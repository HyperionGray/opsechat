"""
Closed-roster room state management for simple_chat_routes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from openpgp_room_policy import normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


def _normalize_key_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("key id must be a string")
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("key id must be non-empty")
    return normalized


def _normalize_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _compute_roster_hash(room_id: str, members: list[dict[str, str]]) -> str:
    canonical_lines = sorted(
        f"{m['member_id']}|{m['signing_fingerprint']}|{m['encryption_fingerprint']}"
        for m in members
    )
    payload = f"opsechat-roster-v1\n{room_id}\n" + "\n".join(canonical_lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


@dataclass
class ClosedRosterState:
    room_id: str

    def __post_init__(self):
        self.room_id = _normalize_text(self.room_id, field_name="room_id")
        self._active_epoch: dict[str, Any] | None = None

    def bootstrap(self, members: list[dict[str, Any]]) -> dict[str, Any]:
        if self._active_epoch is not None:
            raise ValueError("closed roster already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        normalized_members: list[dict[str, str]] = []
        for entry in members:
            if not isinstance(entry, dict):
                raise TypeError("each member must be an object")
            member = {
                "member_id": _normalize_text(entry.get("member_id"), field_name="member_id"),
                "display_name": _normalize_text(
                    entry.get("display_name") or entry.get("member_id"),
                    field_name="display_name",
                ),
                "signing_fingerprint": normalize_fingerprint(entry.get("signing_fingerprint")),
                "encryption_fingerprint": normalize_fingerprint(entry.get("encryption_fingerprint")),
                "signing_key_id": _normalize_key_id(entry.get("signing_key_id")),
                "encryption_key_id": _normalize_key_id(entry.get("encryption_key_id")),
                "public_key_armored": _normalize_text(
                    entry.get("public_key_armored"),
                    field_name="public_key_armored",
                ),
            }
            normalized_members.append(member)

        if len({m["member_id"] for m in normalized_members}) != len(normalized_members):
            raise ValueError("member_id values must be unique")
        if len({m["signing_fingerprint"] for m in normalized_members}) != len(normalized_members):
            raise ValueError("signing fingerprints must be unique")
        if len({m["encryption_fingerprint"] for m in normalized_members}) != len(normalized_members):
            raise ValueError("encryption fingerprints must be unique")
        if len({m["signing_key_id"] for m in normalized_members}) != len(normalized_members):
            raise ValueError("signing key ids must be unique")
        if len({m["encryption_key_id"] for m in normalized_members}) != len(normalized_members):
            raise ValueError("encryption key ids must be unique")

        roster_hash = _compute_roster_hash(self.room_id, normalized_members)
        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": roster_hash,
            "members": normalized_members,
        }
        return self.serialize()

    def serialize(self) -> dict[str, Any]:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.room_id,
            "active_epoch": self._active_epoch,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
        }

    def validate_posted_envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._active_epoch is None:
            raise ValueError("closed roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")

        active_epoch = self._active_epoch
        if active_epoch is None:
            raise RuntimeError("closed roster internal state unavailable")

        envelope_type = payload.get("envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError(f"envelope_type must be {OPENPGP_ENVELOPE_TYPE}")

        if payload.get("room_id") != active_epoch["room_id"]:
            raise ValueError("room_id mismatch")

        if int(payload.get("epoch", 0)) != int(active_epoch["epoch"]):
            raise ValueError("epoch mismatch")

        sender_member_id = _normalize_text(payload.get("sender_member_id"), field_name="sender_member_id")
        sender = next(
            (member for member in active_epoch["members"] if member["member_id"] == sender_member_id),
            None,
        )
        if sender is None:
            raise ValueError("sender is not part of the roster")

        sender_signing_fingerprint = normalize_fingerprint(payload.get("sender_signing_fingerprint"))
        if sender_signing_fingerprint != sender["signing_fingerprint"]:
            raise ValueError("sender signing fingerprint mismatch")

        roster_hash = _normalize_text(payload.get("roster_hash"), field_name="roster_hash").upper()
        if roster_hash != active_epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        expected_fps = {member["encryption_fingerprint"] for member in active_epoch["members"]}
        posted_fps = {
            normalize_fingerprint(fingerprint)
            for fingerprint in payload.get("recipient_encryption_fingerprints") or []
        }
        if posted_fps != expected_fps:
            raise ValueError("recipient set does not match the room roster")

        intended_raw = payload.get("intended_recipient_fingerprints") or []
        intended_fps = {normalize_fingerprint(fingerprint) for fingerprint in intended_raw}
        if intended_fps and intended_fps != expected_fps:
            raise ValueError("intended recipient fingerprints do not match the room roster")

        expected_key_ids = {member["encryption_key_id"] for member in active_epoch["members"]}
        posted_key_ids = {_normalize_key_id(key_id) for key_id in payload.get("recipient_encryption_key_ids") or []}
        if posted_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        armored_message = _normalize_text(payload.get("armored_message"), field_name="armored_message")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "envelope_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": active_epoch["room_id"],
            "epoch": active_epoch["epoch"],
            "sender_member_id": sender_member_id,
            "sender_display_name": sender["display_name"],
            "sender_signing_fingerprint": sender_signing_fingerprint,
            "roster_hash": active_epoch["roster_hash"],
            "recipient_encryption_fingerprints": sorted(expected_fps),
            "intended_recipient_fingerprints": sorted(intended_fps or expected_fps),
            "recipient_encryption_key_ids": sorted(expected_key_ids),
            "armored_message": armored_message,
            "message": armored_message,
        }
