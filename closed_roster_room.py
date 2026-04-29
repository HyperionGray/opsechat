"""
Closed-roster OpenPGP room state and envelope validation helpers.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List

from openpgp_room_policy import normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


def _normalize_key_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("key_id must be a string")
    normalized = "".join(ch for ch in value.strip().upper() if ch in "0123456789ABCDEF")
    if len(normalized) < 8:
        raise ValueError("key_id must be at least 8 hex characters")
    return normalized


def _require_member_field(member: dict, field: str) -> str:
    value = member.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"member field '{field}' is required")
    return value.strip()


class ClosedRosterState:
    """Maintain immutable epoch-1 room roster and validate posted envelopes."""

    def __init__(self, room_id: str):
        self.room_id = str(room_id).strip()
        if not self.room_id:
            raise ValueError("room_id must be non-empty")
        self.active_epoch = None

    def _normalized_members(self, members: list[dict]) -> List[Dict[str, str]]:
        if not isinstance(members, list) or not members:
            raise ValueError("roster must contain at least one member")

        normalized: List[Dict[str, str]] = []
        for raw_member in members:
            if not isinstance(raw_member, dict):
                raise TypeError("member entries must be objects")

            member_id = _require_member_field(raw_member, "member_id")
            display_name = raw_member.get("display_name")
            if not isinstance(display_name, str) or not display_name.strip():
                display_name = member_id

            member = {
                "member_id": member_id,
                "display_name": display_name.strip(),
                "signing_fingerprint": normalize_fingerprint(
                    _require_member_field(raw_member, "signing_fingerprint")
                ),
                "encryption_fingerprint": normalize_fingerprint(
                    _require_member_field(raw_member, "encryption_fingerprint")
                ),
                "signing_key_id": _normalize_key_id(
                    _require_member_field(raw_member, "signing_key_id")
                ),
                "encryption_key_id": _normalize_key_id(
                    _require_member_field(raw_member, "encryption_key_id")
                ),
                "public_key_armored": _require_member_field(raw_member, "public_key_armored"),
            }
            normalized.append(member)

        for field in (
            "member_id",
            "signing_fingerprint",
            "encryption_fingerprint",
            "signing_key_id",
            "encryption_key_id",
        ):
            values = [member[field] for member in normalized]
            if len(values) != len(set(values)):
                raise ValueError(f"{field} values must be unique within a roster")

        return sorted(normalized, key=lambda item: item["member_id"])

    def _roster_hash_for_members(self, members: List[Dict[str, str]]) -> str:
        digest = hashlib.sha256()
        digest.update(f"{self.room_id}|1|{OPENPGP_ENVELOPE_TYPE}\n".encode("utf-8"))
        for member in members:
            digest.update(
                (
                    f"{member['member_id']}|{member['display_name']}|"
                    f"{member['signing_fingerprint']}|{member['encryption_fingerprint']}|"
                    f"{member['signing_key_id']}|{member['encryption_key_id']}\n"
                ).encode("utf-8")
            )
        return digest.hexdigest().upper()

    def bootstrap(self, members: list[dict]) -> dict:
        if self.active_epoch is not None:
            raise ValueError("room roster is already initialized")

        normalized_members = self._normalized_members(members)
        roster_hash = self._roster_hash_for_members(normalized_members)
        self.active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": roster_hash,
            "members": normalized_members,
        }
        return self.serialize()

    def serialize(self) -> dict:
        active_epoch = None
        if self.active_epoch is not None:
            active_epoch = {
                "room_id": self.active_epoch["room_id"],
                "epoch": self.active_epoch["epoch"],
                "immutable_roster": True,
                "roster_hash": self.active_epoch["roster_hash"],
                "members": [dict(member) for member in self.active_epoch["members"]],
            }

        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": active_epoch,
        }

    def validate_posted_envelope(self, payload: dict) -> dict:
        if self.active_epoch is None:
            raise ValueError("closed roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")

        if payload.get("envelope_type") != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("unsupported envelope_type")

        if payload.get("room_id") != self.active_epoch["room_id"]:
            raise ValueError("room_id mismatch")
        if payload.get("epoch") != self.active_epoch["epoch"]:
            raise ValueError("epoch mismatch")

        roster_hash = str(payload.get("roster_hash", "")).strip().upper()
        if roster_hash != self.active_epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        sender_member_id = payload.get("sender_member_id")
        if not isinstance(sender_member_id, str) or not sender_member_id.strip():
            raise ValueError("sender_member_id is required")
        sender_member_id = sender_member_id.strip()

        members_by_id = {
            member["member_id"]: member for member in self.active_epoch["members"]
        }
        sender = members_by_id.get(sender_member_id)
        if sender is None:
            raise ValueError("sender is not part of the room roster")

        sender_signing_fingerprint = normalize_fingerprint(
            str(payload.get("sender_signing_fingerprint", "")).strip()
        )
        if sender_signing_fingerprint != sender["signing_fingerprint"]:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipient_fps = {
            member["encryption_fingerprint"] for member in self.active_epoch["members"]
        }
        actual_recipient_fps = {
            normalize_fingerprint(value)
            for value in (payload.get("recipient_encryption_fingerprints") or [])
        }
        if actual_recipient_fps != expected_recipient_fps:
            raise ValueError("recipient set does not match the room roster")

        intended = payload.get("intended_recipient_fingerprints")
        if intended:
            intended_fps = {normalize_fingerprint(value) for value in intended}
            if intended_fps != expected_recipient_fps:
                raise ValueError("intended recipient fingerprints do not match the room roster")

        expected_key_ids = {
            member["encryption_key_id"] for member in self.active_epoch["members"]
        }
        actual_key_ids = {
            _normalize_key_id(value)
            for value in (payload.get("recipient_encryption_key_ids") or [])
        }
        if actual_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        armored_message = payload.get("armored_message")
        if not isinstance(armored_message, str) or not armored_message.strip():
            raise ValueError("armored_message is required")
        armored_message = armored_message.strip()

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.active_epoch["room_id"],
            "epoch": self.active_epoch["epoch"],
            "sender_member_id": sender_member_id,
            "sender_display_name": sender["display_name"],
            "sender_signing_fingerprint": sender_signing_fingerprint,
            "roster_hash": self.active_epoch["roster_hash"],
            "recipient_encryption_fingerprints": [
                member["encryption_fingerprint"] for member in self.active_epoch["members"]
            ],
            "intended_recipient_fingerprints": [
                member["encryption_fingerprint"] for member in self.active_epoch["members"]
            ],
            "recipient_encryption_key_ids": [
                member["encryption_key_id"] for member in self.active_epoch["members"]
            ],
            "armored_message": armored_message,
            # Keep `message` for compatibility with existing room/message serialization.
            "message": armored_message,
        }
