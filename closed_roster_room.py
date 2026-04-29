"""
Compatibility helpers for the closed-roster OpenPGP room flow.

This module provides the interface expected by simple_chat_routes and tests:
- OPENPGP_ENVELOPE_TYPE constant
- ClosedRosterState with bootstrap(), serialize(), validate_posted_envelope()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from openpgp_room_policy import RoomEpoch, RoomMember, canonicalize_roster


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


def _normalize_required_string(value: str) -> str:
    """Return a stripped non-empty string."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must be non-empty")
    return normalized


@dataclass(frozen=True)
class _MemberRecord:
    """Internal canonical member details plus transport metadata."""

    member: RoomMember
    signing_key_id: str
    encryption_key_id: str
    public_key_armored: str

    @property
    def member_id(self) -> str:
        return self.member.member_id

    def to_dict(self) -> Dict[str, str]:
        return {
            "member_id": self.member.member_id,
            "display_name": self.member.display_name,
            "signing_fingerprint": self.member.signing_fingerprint,
            "encryption_fingerprint": self.member.encryption_fingerprint,
            "signing_key_id": self.signing_key_id,
            "encryption_key_id": self.encryption_key_id,
            "public_key_armored": self.public_key_armored,
        }


class ClosedRosterState:
    """Immutable closed-roster state for one room."""

    def __init__(self, room_id: str):
        self._room_id = _normalize_required_string(room_id)
        self._active_epoch: Optional[RoomEpoch] = None
        self._members: List[_MemberRecord] = []
        self._member_by_id: Dict[str, _MemberRecord] = {}

    def bootstrap(self, members: List[Dict]) -> Dict:
        if self._active_epoch is not None:
            raise ValueError("room roster already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        parsed_records: List[_MemberRecord] = []
        for raw_member in members:
            if not isinstance(raw_member, dict):
                raise TypeError("member record must be an object")
            room_member = RoomMember(
                member_id=_normalize_required_string(
                    raw_member.get("member_id", "")
                ),
                display_name=_normalize_required_string(
                    raw_member.get("display_name")
                    or raw_member.get("member_id", "")
                ),
                signing_fingerprint=_normalize_required_string(
                    raw_member.get("signing_fingerprint", "")
                ),
                encryption_fingerprint=_normalize_required_string(
                    raw_member.get("encryption_fingerprint", "")
                ),
            )
            parsed_records.append(
                _MemberRecord(
                    member=room_member,
                    signing_key_id=_normalize_required_string(
                        raw_member.get("signing_key_id", "")
                    ),
                    encryption_key_id=_normalize_required_string(
                        raw_member.get("encryption_key_id", "")
                    ),
                    public_key_armored=_normalize_required_string(
                        raw_member.get("public_key_armored", "")
                    ),
                )
            )

        canonical_members = list(
            canonicalize_roster([record.member for record in parsed_records])
        )
        record_by_member = {record.member: record for record in parsed_records}
        self._members = [
            record_by_member[member]
            for member in canonical_members
        ]
        self._member_by_id = {
            record.member_id: record
            for record in self._members
        }
        self._active_epoch = RoomEpoch(
            room_id=self._room_id,
            epoch=1,
            members=tuple(canonical_members),
        )
        return self.serialize()

    def serialize(self) -> Dict:
        epoch = self._active_epoch
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": (
                None
                if epoch is None
                else self._serialize_epoch(epoch)
            ),
        }

    def validate_posted_envelope(self, payload: Dict) -> Dict:
        if self._active_epoch is None:
            raise ValueError("closed roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")
        if payload.get("envelope_type") != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("unsupported envelope type")

        epoch = self._active_epoch

        room_id = _normalize_required_string(payload.get("room_id", ""))
        if room_id != epoch.room_id:
            raise ValueError("room_id mismatch")

        try:
            message_epoch = int(payload.get("epoch"))
        except (TypeError, ValueError):
            raise ValueError("epoch must be an integer")
        if message_epoch != epoch.epoch:
            raise ValueError("epoch mismatch")

        roster_hash = _normalize_required_string(
            payload.get("roster_hash", "")
        )
        if roster_hash != epoch.roster_hash:
            raise ValueError("roster hash mismatch")

        sender_member_id = _normalize_required_string(
            payload.get("sender_member_id", "")
        )
        sender = self._member_by_id.get(sender_member_id)
        if sender is None:
            raise ValueError("sender is not part of the roster")

        sender_signing_fingerprint = _normalize_required_string(
            payload.get("sender_signing_fingerprint", "")
        ).upper()
        if sender_signing_fingerprint != sender.member.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipient_fps = sorted(
            member.member.encryption_fingerprint for member in self._members
        )
        posted_recipient_fps = sorted(
            _normalize_required_string(value).upper()
            for value in payload.get("recipient_encryption_fingerprints", [])
        )
        if posted_recipient_fps != expected_recipient_fps:
            raise ValueError("recipient set does not match the room roster")

        posted_intended = payload.get("intended_recipient_fingerprints")
        if posted_intended is not None:
            normalized_intended = sorted(
                _normalize_required_string(value).upper()
                for value in posted_intended
            )
            if normalized_intended != expected_recipient_fps:
                raise ValueError(
                    (
                        "intended recipient fingerprints "
                        "do not match the room roster"
                    )
                )

        expected_key_ids = sorted(
            member.encryption_key_id.upper() for member in self._members
        )
        posted_key_ids = sorted(
            _normalize_required_string(value).upper()
            for value in payload.get("recipient_encryption_key_ids", [])
        )
        if posted_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match")

        armored_message = _normalize_required_string(
            payload.get("armored_message", "")
        )

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "armored_message": armored_message,
            "message": armored_message,
            "sender_member_id": sender.member_id,
            "sender_display_name": sender.member.display_name,
            "sender_signing_fingerprint": sender.member.signing_fingerprint,
            "epoch": epoch.epoch,
            "roster_hash": epoch.roster_hash,
            "recipient_encryption_fingerprints": expected_recipient_fps,
            "recipient_encryption_key_ids": expected_key_ids,
        }

    def _serialize_epoch(self, epoch: RoomEpoch) -> Dict:
        return {
            "room_id": epoch.room_id,
            "epoch": epoch.epoch,
            "immutable_roster": True,
            "roster_hash": epoch.roster_hash,
            "members": [member.to_dict() for member in self._members],
        }
