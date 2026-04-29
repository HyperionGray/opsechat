"""
Closed-roster room state helpers for simple_chat_routes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openpgp_room_policy import RoomMember, hash_roster, normalize_fingerprint

OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


@dataclass(frozen=True)
class _RosterMember:
    member_id: str
    display_name: str
    signing_fingerprint: str
    encryption_fingerprint: str
    signing_key_id: str
    encryption_key_id: str
    public_key_armored: str

    def to_dict(self) -> dict[str, str]:
        return {
            "member_id": self.member_id,
            "display_name": self.display_name,
            "signing_fingerprint": self.signing_fingerprint,
            "encryption_fingerprint": self.encryption_fingerprint,
            "signing_key_id": self.signing_key_id,
            "encryption_key_id": self.encryption_key_id,
            "public_key_armored": self.public_key_armored,
        }


def _normalized_key_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


class ClosedRosterState:
    """Immutable epoch-1 roster state for the current room."""

    def __init__(self, room_id: str):
        if not isinstance(room_id, str) or not room_id.strip():
            raise ValueError("room_id must be a non-empty string")
        self.room_id = room_id.strip()
        self._active_epoch: dict[str, Any] | None = None
        self._members_by_id: dict[str, _RosterMember] = {}
        self._expected_recipient_fingerprints: set[str] = set()
        self._expected_recipient_key_ids: set[str] = set()

    def _normalized_members(self, members: Any) -> list[_RosterMember]:
        if not isinstance(members, list):
            raise TypeError("members must be a list")
        if not members:
            raise ValueError("members must contain at least one member")

        normalized: list[_RosterMember] = []
        for entry in members:
            if not isinstance(entry, dict):
                raise TypeError("member entries must be objects")
            member_id = str(entry.get("member_id", "")).strip()
            if not member_id:
                raise ValueError("member_id must be non-empty")
            display_name = str(entry.get("display_name") or member_id).strip() or member_id
            signing_fingerprint = normalize_fingerprint(entry.get("signing_fingerprint"))
            encryption_fingerprint = normalize_fingerprint(entry.get("encryption_fingerprint"))
            signing_key_id = _normalized_key_id(entry.get("signing_key_id"), "signing_key_id")
            encryption_key_id = _normalized_key_id(entry.get("encryption_key_id"), "encryption_key_id")
            public_key_armored = str(entry.get("public_key_armored", "")).strip()
            if not public_key_armored:
                raise ValueError("public_key_armored must be non-empty")

            normalized.append(
                _RosterMember(
                    member_id=member_id,
                    display_name=display_name,
                    signing_fingerprint=signing_fingerprint,
                    encryption_fingerprint=encryption_fingerprint,
                    signing_key_id=signing_key_id,
                    encryption_key_id=encryption_key_id,
                    public_key_armored=public_key_armored,
                )
            )

        if len({member.member_id for member in normalized}) != len(normalized):
            raise ValueError("member ids must be unique")
        if len({member.signing_fingerprint for member in normalized}) != len(normalized):
            raise ValueError("signing fingerprints must be unique")
        if len({member.encryption_fingerprint for member in normalized}) != len(normalized):
            raise ValueError("encryption fingerprints must be unique")
        if len({member.encryption_key_id for member in normalized}) != len(normalized):
            raise ValueError("encryption key ids must be unique")

        return sorted(normalized, key=lambda member: member.member_id)

    def _require_active_epoch(self) -> dict[str, Any]:
        if self._active_epoch is None:
            raise ValueError("closed roster not initialized")
        return self._active_epoch

    def bootstrap(self, members: Any) -> dict[str, Any]:
        if self._active_epoch is not None:
            raise ValueError("closed roster already initialized")

        normalized = self._normalized_members(members)
        policy_members = tuple(
            RoomMember(
                member_id=member.member_id,
                display_name=member.display_name,
                signing_fingerprint=member.signing_fingerprint,
                encryption_fingerprint=member.encryption_fingerprint,
            )
            for member in normalized
        )
        roster_hash = hash_roster(policy_members)

        self._members_by_id = {member.member_id: member for member in normalized}
        self._expected_recipient_fingerprints = {
            member.encryption_fingerprint for member in normalized
        }
        self._expected_recipient_key_ids = {
            member.encryption_key_id for member in normalized
        }

        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": roster_hash,
            "members": [member.to_dict() for member in normalized],
        }
        return self.serialize()

    def serialize(self) -> dict[str, Any]:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self._active_epoch,
        }

    def validate_posted_envelope(self, payload: Any) -> dict[str, Any]:
        epoch = self._require_active_epoch()
        if not isinstance(payload, dict):
            raise TypeError("message payload must be a JSON object")

        envelope_type = str(payload.get("envelope_type", "")).strip()
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("unsupported envelope type")
        if str(payload.get("room_id", "")).strip() != self.room_id:
            raise ValueError("room id mismatch")
        if int(payload.get("epoch", 0)) != int(epoch["epoch"]):
            raise ValueError("epoch mismatch")
        if str(payload.get("roster_hash", "")).strip().upper() != epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        sender_member_id = str(payload.get("sender_member_id", "")).strip()
        sender = self._members_by_id.get(sender_member_id)
        if sender is None:
            raise ValueError("sender member id is not part of roster")

        sender_signing_fingerprint = normalize_fingerprint(
            payload.get("sender_signing_fingerprint")
        )
        if sender_signing_fingerprint != sender.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        recipient_encryption_fingerprints = {
            normalize_fingerprint(item)
            for item in payload.get("recipient_encryption_fingerprints", [])
        }
        if recipient_encryption_fingerprints != self._expected_recipient_fingerprints:
            raise ValueError("recipient set does not match the room roster")

        intended_recipient_fingerprints = {
            normalize_fingerprint(item)
            for item in payload.get("intended_recipient_fingerprints", [])
        }
        if (
            intended_recipient_fingerprints
            and intended_recipient_fingerprints != self._expected_recipient_fingerprints
        ):
            raise ValueError("intended recipient fingerprints do not match the room roster")

        recipient_encryption_key_ids = {
            _normalized_key_id(item, "recipient_encryption_key_id")
            for item in payload.get("recipient_encryption_key_ids", [])
        }
        if recipient_encryption_key_ids != self._expected_recipient_key_ids:
            raise ValueError("recipient encryption key ids do not match")

        armored_message = str(payload.get("armored_message", "")).strip()
        if not armored_message:
            raise ValueError("armored message must be non-empty")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "envelope_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.room_id,
            "epoch": epoch["epoch"],
            "sender_member_id": sender.member_id,
            "sender_display_name": sender.display_name,
            "sender_signing_fingerprint": sender.signing_fingerprint,
            "roster_hash": epoch["roster_hash"],
            "recipient_encryption_fingerprints": sorted(self._expected_recipient_fingerprints),
            "intended_recipient_fingerprints": sorted(
                intended_recipient_fingerprints or self._expected_recipient_fingerprints
            ),
            "recipient_encryption_key_ids": sorted(self._expected_recipient_key_ids),
            "armored_message": armored_message,
            "message": armored_message,
        }
