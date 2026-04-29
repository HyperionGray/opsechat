"""
Closed-roster room state management for OpenPGP-based secure chat.

This module provides a small state container for immutable epoch-1 room roster
bootstrap and payload validation for OpenPGP envelope metadata.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from openpgp_room_policy import normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "opsechat.closed-roster-openpgp-envelope.v1"


def _normalize_key_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("key id must be a string")
    normalized = "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")
    if len(normalized) < 8:
        raise ValueError("key id must contain at least 8 hex characters")
    return normalized


@dataclass(frozen=True)
class _RosterMember:
    member_id: str
    display_name: str
    signing_fingerprint: str
    encryption_fingerprint: str
    signing_key_id: str
    encryption_key_id: str
    public_key_armored: str


class ClosedRosterState:
    """Per-room immutable roster state for closed-roster OpenPGP chat."""

    def __init__(self, room_id: str):
        self.room_id = room_id
        self._active_epoch: dict[str, Any] | None = None
        self._members_by_id: dict[str, _RosterMember] = {}

    def serialize(self) -> dict[str, Any]:
        active_epoch = None
        if self._active_epoch is not None:
            active_epoch = {
                "room_id": self._active_epoch["room_id"],
                "epoch": self._active_epoch["epoch"],
                "roster_hash": self._active_epoch["roster_hash"],
                "immutable_roster": self._active_epoch["immutable_roster"],
                "members": [member.copy() for member in self._active_epoch["members"]],
            }

        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "active_epoch": active_epoch,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
        }

    def bootstrap(self, members: list[dict[str, Any]]) -> dict[str, Any]:
        if self._active_epoch is not None:
            raise ValueError("closed roster already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        parsed_members: list[_RosterMember] = []
        member_ids_seen: set[str] = set()
        signing_fps_seen: set[str] = set()
        encryption_fps_seen: set[str] = set()

        for raw in members:
            if not isinstance(raw, dict):
                raise TypeError("each member must be an object")

            member_id = str(raw.get("member_id", "")).strip()
            if not member_id:
                raise ValueError("member_id must be non-empty")
            if member_id in member_ids_seen:
                raise ValueError("member_id values must be unique")
            member_ids_seen.add(member_id)

            signing_fp = normalize_fingerprint(raw.get("signing_fingerprint", ""))
            encryption_fp = normalize_fingerprint(raw.get("encryption_fingerprint", ""))

            if signing_fp in signing_fps_seen:
                raise ValueError("signing fingerprints must be unique")
            if encryption_fp in encryption_fps_seen:
                raise ValueError("encryption fingerprints must be unique")
            signing_fps_seen.add(signing_fp)
            encryption_fps_seen.add(encryption_fp)

            signing_key_id = _normalize_key_id(
                str(raw.get("signing_key_id") or signing_fp[:16])
            )
            encryption_key_id = _normalize_key_id(
                str(raw.get("encryption_key_id") or encryption_fp[:16])
            )

            parsed_members.append(
                _RosterMember(
                    member_id=member_id,
                    display_name=str(raw.get("display_name") or member_id),
                    signing_fingerprint=signing_fp,
                    encryption_fingerprint=encryption_fp,
                    signing_key_id=signing_key_id,
                    encryption_key_id=encryption_key_id,
                    public_key_armored=str(raw.get("public_key_armored") or ""),
                )
            )

        canonical_members = sorted(
            parsed_members,
            key=lambda member: (
                member.signing_fingerprint,
                member.encryption_fingerprint,
                member.member_id,
            ),
        )
        roster_payload = "\n".join(
            f"{m.member_id}|{m.signing_fingerprint}|{m.encryption_fingerprint}"
            for m in canonical_members
        )

        roster_hash = hashlib.sha256(
            f"opsechat-roster-v1\n{roster_payload}".encode("utf-8")
        ).hexdigest().upper()

        self._members_by_id = {member.member_id: member for member in canonical_members}
        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "roster_hash": roster_hash,
            "immutable_roster": True,
            "members": [
                {
                    "member_id": member.member_id,
                    "display_name": member.display_name,
                    "signing_fingerprint": member.signing_fingerprint,
                    "encryption_fingerprint": member.encryption_fingerprint,
                    "signing_key_id": member.signing_key_id,
                    "encryption_key_id": member.encryption_key_id,
                    "public_key_armored": member.public_key_armored,
                }
                for member in canonical_members
            ],
        }
        return self.serialize()

    def validate_posted_envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._active_epoch is None:
            raise ValueError("closed roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("payload must be an object")

        envelope_type = payload.get("envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("invalid envelope_type")

        if payload.get("room_id") != self._active_epoch["room_id"]:
            raise ValueError("room_id mismatch")
        if payload.get("epoch") != self._active_epoch["epoch"]:
            raise ValueError("epoch mismatch")
        if payload.get("roster_hash") != self._active_epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        sender_member_id = str(payload.get("sender_member_id", "")).strip()
        sender_member = self._members_by_id.get(sender_member_id)
        if not sender_member:
            raise ValueError("sender is not part of the roster")

        sender_fp = normalize_fingerprint(payload.get("sender_signing_fingerprint", ""))
        if sender_fp != sender_member.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipient_fps = {
            member.encryption_fingerprint for member in self._members_by_id.values()
        }
        posted_recipient_fps = {
            normalize_fingerprint(fp)
            for fp in payload.get("recipient_encryption_fingerprints", [])
        }
        if posted_recipient_fps != expected_recipient_fps:
            raise ValueError("recipient set does not match the room roster")

        intended_recipients = payload.get("intended_recipient_fingerprints", [])
        if intended_recipients:
            posted_intended_fps = {
                normalize_fingerprint(fp) for fp in intended_recipients
            }
            if posted_intended_fps != expected_recipient_fps:
                raise ValueError(
                    "intended recipient fingerprints do not match the room roster"
                )

        expected_recipient_key_ids = {
            member.encryption_key_id for member in self._members_by_id.values()
        }
        posted_recipient_key_ids = {
            _normalize_key_id(key_id)
            for key_id in payload.get("recipient_encryption_key_ids", [])
        }
        if posted_recipient_key_ids != expected_recipient_key_ids:
            raise ValueError("recipient encryption key ids do not match")

        armored_message = payload.get("armored_message")
        if not isinstance(armored_message, str) or not armored_message.strip():
            raise ValueError("armored_message is required")
        if (
            "-----BEGIN PGP MESSAGE-----" not in armored_message
            or "-----END PGP MESSAGE-----" not in armored_message
        ):
            raise ValueError("armored_message must be an ASCII-armored PGP message")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": self._active_epoch["room_id"],
            "epoch": self._active_epoch["epoch"],
            "sender_member_id": sender_member.member_id,
            "sender_display_name": sender_member.display_name,
            "sender_signing_fingerprint": sender_member.signing_fingerprint,
            "roster_hash": self._active_epoch["roster_hash"],
            "recipient_encryption_fingerprints": sorted(expected_recipient_fps),
            "intended_recipient_fingerprints": sorted(expected_recipient_fps),
            "recipient_encryption_key_ids": sorted(expected_recipient_key_ids),
            "armored_message": armored_message.strip(),
            "anonymous_recipients": False,
        }
