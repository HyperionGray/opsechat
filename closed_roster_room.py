"""
Closed-roster OpenPGP room state helpers.

Provides a minimal immutable roster model for epoch-1 chat rooms and
validation for posted encrypted message envelopes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"

_MEMBER_FIELDS = (
    "member_id",
    "display_name",
    "signing_fingerprint",
    "encryption_fingerprint",
    "signing_key_id",
    "encryption_key_id",
    "public_key_armored",
)


class ClosedRosterState:
    """Immutable epoch-1 closed-roster state for a room."""

    def __init__(self, room_id: str):
        self.room_id = room_id
        self._active_epoch: dict[str, Any] | None = None

    def serialize(self) -> dict[str, Any]:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self._active_epoch,
        }

    def bootstrap(self, members: list[dict[str, Any]]) -> dict[str, Any]:
        if self._active_epoch is not None:
            raise ValueError("Closed roster already initialized")
        if not isinstance(members, list) or not members:
            raise TypeError("members must be a non-empty list")

        normalized_members: list[dict[str, str]] = []
        seen_member_ids: set[str] = set()
        for member in members:
            if not isinstance(member, dict):
                raise TypeError("Each member must be an object")
            normalized: dict[str, str] = {}
            for field in _MEMBER_FIELDS:
                value = member.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Missing required member field: {field}")
                normalized[field] = value.strip()

            member_id = normalized["member_id"]
            if member_id in seen_member_ids:
                raise ValueError(f"Duplicate member_id: {member_id}")
            seen_member_ids.add(member_id)
            normalized_members.append(normalized)

        roster_hash = _compute_roster_hash(self.room_id, 1, normalized_members)
        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": roster_hash,
            "members": normalized_members,
        }
        return self.serialize()

    def validate_posted_envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._active_epoch is None:
            raise ValueError("Closed roster not initialized")
        if not isinstance(payload, dict):
            raise TypeError("payload must be an object")

        epoch = self._active_epoch
        envelope_type = payload.get("envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("invalid envelope type")
        if payload.get("room_id") != epoch["room_id"]:
            raise ValueError("room id mismatch")
        if payload.get("epoch") != epoch["epoch"]:
            raise ValueError("epoch mismatch")
        if payload.get("roster_hash") != epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        sender_member_id = payload.get("sender_member_id")
        sender = self._member_by_id(str(sender_member_id))
        if sender is None:
            raise ValueError("unknown sender member")

        sender_fp = payload.get("sender_signing_fingerprint")
        if sender_fp != sender["signing_fingerprint"]:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipient_fps = {m["encryption_fingerprint"] for m in epoch["members"]}
        recipient_fps = payload.get("recipient_encryption_fingerprints")
        if set(_as_string_list(recipient_fps)) != expected_recipient_fps:
            raise ValueError("recipient set does not match")

        intended_fps = payload.get("intended_recipient_fingerprints")
        if set(_as_string_list(intended_fps)) != expected_recipient_fps:
            raise ValueError("recipient set does not match")

        expected_key_ids = {m["encryption_key_id"] for m in epoch["members"]}
        key_ids = payload.get("recipient_encryption_key_ids")
        if set(_as_string_list(key_ids)) != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match")

        armored_message = payload.get("armored_message")
        if not isinstance(armored_message, str) or not armored_message.strip():
            raise ValueError("missing armored message")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": epoch["room_id"],
            "epoch": epoch["epoch"],
            "roster_hash": epoch["roster_hash"],
            "sender_member_id": sender["member_id"],
            "sender_display_name": sender["display_name"],
            "sender_signing_fingerprint": sender["signing_fingerprint"],
            "armored_message": armored_message.strip(),
        }

    def _member_by_id(self, member_id: str) -> dict[str, str] | None:
        if self._active_epoch is None:
            return None
        for member in self._active_epoch["members"]:
            if member["member_id"] == member_id:
                return member
        return None


def _compute_roster_hash(room_id: str, epoch: int, members: list[dict[str, str]]) -> str:
    canonical = {
        "room_id": room_id,
        "epoch": epoch,
        "members": sorted(
            members,
            key=lambda m: (
                m["member_id"],
                m["signing_fingerprint"],
                m["encryption_fingerprint"],
            ),
        ),
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        return []
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        strings.append(item.strip())
    return strings
