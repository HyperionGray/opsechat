"""
Closed-roster room state and envelope validation helpers.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List

from openpgp_room_policy import RoomMember, hash_roster, normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


@dataclass(frozen=True)
class _RosterMemberRecord:
    member_id: str
    display_name: str
    signing_fingerprint: str
    encryption_fingerprint: str
    signing_key_id: str
    encryption_key_id: str
    public_key_armored: str

    def as_dict(self) -> dict:
        return {
            "member_id": self.member_id,
            "display_name": self.display_name,
            "signing_fingerprint": self.signing_fingerprint,
            "encryption_fingerprint": self.encryption_fingerprint,
            "signing_key_id": self.signing_key_id,
            "encryption_key_id": self.encryption_key_id,
            "public_key_armored": self.public_key_armored,
        }


def _normalize_non_empty_str(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _normalize_key_id(value: object, field_name: str) -> str:
    normalized = _normalize_non_empty_str(value, field_name)
    return "".join(ch for ch in normalized.upper() if ch.isalnum())


class ClosedRosterState:
    """Immutable epoch-1 roster and encrypted envelope validation."""

    def __init__(self, room_id: str):
        self.room_id = _normalize_non_empty_str(room_id, "room_id")
        self._active_epoch: dict | None = None
        self._members_by_id: Dict[str, _RosterMemberRecord] = {}

    def bootstrap(self, members: List[dict]) -> dict:
        if self._active_epoch is not None:
            raise ValueError("room roster already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        parsed_members: List[_RosterMemberRecord] = []
        seen_member_ids = set()
        seen_signing_fps = set()
        seen_encryption_fps = set()
        seen_encryption_key_ids = set()

        for index, member in enumerate(members):
            if not isinstance(member, dict):
                raise TypeError(f"members[{index}] must be an object")

            member_id = _normalize_non_empty_str(member.get("member_id"), "member_id")
            display_name = _normalize_non_empty_str(
                member.get("display_name", member_id),
                "display_name",
            )
            signing_fingerprint = normalize_fingerprint(
                member.get("signing_fingerprint")
            )
            encryption_fingerprint = normalize_fingerprint(
                member.get("encryption_fingerprint")
            )
            signing_key_id = _normalize_key_id(member.get("signing_key_id"), "signing_key_id")
            encryption_key_id = _normalize_key_id(
                member.get("encryption_key_id"),
                "encryption_key_id",
            )
            public_key_armored = _normalize_non_empty_str(
                member.get("public_key_armored"),
                "public_key_armored",
            )

            if member_id in seen_member_ids:
                raise ValueError("member_id values must be unique")
            if signing_fingerprint in seen_signing_fps:
                raise ValueError("signing fingerprints must be unique")
            if encryption_fingerprint in seen_encryption_fps:
                raise ValueError("encryption fingerprints must be unique")
            if encryption_key_id in seen_encryption_key_ids:
                raise ValueError("encryption key ids must be unique")

            seen_member_ids.add(member_id)
            seen_signing_fps.add(signing_fingerprint)
            seen_encryption_fps.add(encryption_fingerprint)
            seen_encryption_key_ids.add(encryption_key_id)
            parsed_members.append(
                _RosterMemberRecord(
                    member_id=member_id,
                    display_name=display_name,
                    signing_fingerprint=signing_fingerprint,
                    encryption_fingerprint=encryption_fingerprint,
                    signing_key_id=signing_key_id,
                    encryption_key_id=encryption_key_id,
                    public_key_armored=public_key_armored,
                )
            )

        parsed_members.sort(key=lambda m: m.member_id)
        room_members = [
            RoomMember(
                member_id=m.member_id,
                display_name=m.display_name,
                signing_fingerprint=m.signing_fingerprint,
                encryption_fingerprint=m.encryption_fingerprint,
            )
            for m in parsed_members
        ]
        self._members_by_id = {member.member_id: member for member in parsed_members}
        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": hash_roster(room_members),
            "members": [member.as_dict() for member in parsed_members],
        }
        return self.serialize()

    def serialize(self) -> dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "active_epoch": deepcopy(self._active_epoch),
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
        }

    def validate_posted_envelope(self, payload: dict) -> dict:
        if self._active_epoch is None:
            raise ValueError("room roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be a JSON object")

        envelope_type = _normalize_non_empty_str(payload.get("envelope_type"), "envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("unsupported envelope_type")

        room_id = _normalize_non_empty_str(payload.get("room_id"), "room_id")
        if room_id != self.room_id:
            raise ValueError("room_id mismatch")

        epoch = payload.get("epoch")
        if not isinstance(epoch, int):
            raise TypeError("epoch must be an integer")
        if epoch != int(self._active_epoch["epoch"]):
            raise ValueError("epoch mismatch")

        roster_hash = _normalize_non_empty_str(payload.get("roster_hash"), "roster_hash")
        if roster_hash != self._active_epoch["roster_hash"]:
            raise ValueError("roster_hash mismatch")

        sender_member_id = _normalize_non_empty_str(
            payload.get("sender_member_id"),
            "sender_member_id",
        )
        sender = self._members_by_id.get(sender_member_id)
        if sender is None:
            raise ValueError("sender member is not in roster")

        sender_signing_fingerprint = normalize_fingerprint(
            payload.get("sender_signing_fingerprint")
        )
        if sender_signing_fingerprint != sender.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        recipient_fps = payload.get("recipient_encryption_fingerprints")
        intended_fps = payload.get("intended_recipient_fingerprints")
        if not isinstance(recipient_fps, list) or not recipient_fps:
            raise ValueError("recipient_encryption_fingerprints must be a non-empty list")
        if not isinstance(intended_fps, list) or not intended_fps:
            raise ValueError("intended_recipient_fingerprints must be a non-empty list")

        expected_fps = {
            member.encryption_fingerprint for member in self._members_by_id.values()
        }
        normalized_recipient_fps = {normalize_fingerprint(item) for item in recipient_fps}
        normalized_intended_fps = {normalize_fingerprint(item) for item in intended_fps}
        if normalized_recipient_fps != expected_fps:
            raise ValueError("recipient set does not match room roster")
        if normalized_intended_fps != expected_fps:
            raise ValueError("recipient set does not match room roster")

        recipient_key_ids = payload.get("recipient_encryption_key_ids")
        if not isinstance(recipient_key_ids, list) or not recipient_key_ids:
            raise ValueError("recipient_encryption_key_ids must be a non-empty list")
        normalized_recipient_key_ids = {
            _normalize_key_id(item, "recipient_encryption_key_ids")
            for item in recipient_key_ids
        }
        expected_key_ids = {
            member.encryption_key_id for member in self._members_by_id.values()
        }
        if (
            normalized_recipient_key_ids != expected_key_ids
            or len(recipient_key_ids) != len(expected_key_ids)
        ):
            raise ValueError("recipient encryption key ids do not match")

        armored_message = _normalize_non_empty_str(payload.get("armored_message"), "armored_message")
        if "-----BEGIN PGP MESSAGE-----" not in armored_message:
            raise ValueError("armored_message must contain a PGP message block")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "envelope_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.room_id,
            "epoch": epoch,
            "sender_member_id": sender.member_id,
            "sender_display_name": sender.display_name,
            "sender_signing_fingerprint": sender.signing_fingerprint,
            "roster_hash": roster_hash,
            "recipient_encryption_fingerprints": sorted(normalized_recipient_fps),
            "intended_recipient_fingerprints": sorted(normalized_intended_fps),
            "recipient_encryption_key_ids": sorted(normalized_recipient_key_ids),
            "armored_message": armored_message,
            "message": armored_message,
        }
