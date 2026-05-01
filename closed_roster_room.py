"""
Closed-roster OpenPGP room state for simple chat rooms.

The server does not decrypt room traffic. Its job is to:

- freeze an immutable epoch-1 roster for a room
- expose that roster to the browser UI
- reject uploaded envelope metadata that does not match the active roster

Actual OpenPGP encryption, decryption, and signature verification happen in the
browser via `static/chat-room.js`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from openpgp_room_policy import RoomEpoch, RoomMember, normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"

_HEX = set("0123456789ABCDEF")
_KEY_ID_LENGTHS = {16}


def _normalize_key_id(value: str, field_name: str) -> str:
    """Normalize an OpenPGP key id to uppercase hex."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = "".join(ch for ch in value.upper() if ch in _HEX)
    if len(normalized) not in _KEY_ID_LENGTHS:
        raise ValueError(f"{field_name} must be 16 hex characters after normalization")
    return normalized


def _normalize_room_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("room_id must be a string")

    normalized = value.strip()
    if not normalized:
        raise ValueError("room_id must be non-empty")
    return normalized


def _normalize_fingerprint_list(values, field_name: str) -> frozenset[str]:
    if not isinstance(values, list):
        raise TypeError(f"{field_name} must be a list")
    return frozenset(normalize_fingerprint(value) for value in values)


def _normalize_key_id_list(values, field_name: str) -> frozenset[str]:
    if not isinstance(values, list):
        raise TypeError(f"{field_name} must be a list")
    return frozenset(_normalize_key_id(value, field_name) for value in values)


@dataclass(frozen=True)
class ClosedRosterMemberRecord:
    """Full roster record exposed to the UI for one room member."""

    room_member: RoomMember
    signing_key_id: str
    encryption_key_id: str
    public_key_armored: str

    @classmethod
    def from_payload(cls, payload: dict) -> "ClosedRosterMemberRecord":
        if not isinstance(payload, dict):
            raise TypeError("roster member must be an object")

        public_key_armored = payload.get("public_key_armored")
        if not isinstance(public_key_armored, str) or not public_key_armored.strip():
            raise ValueError("public_key_armored must be a non-empty string")

        member = RoomMember(
            member_id=payload.get("member_id"),
            signing_fingerprint=payload.get("signing_fingerprint"),
            encryption_fingerprint=payload.get("encryption_fingerprint"),
            display_name=payload.get("display_name") or payload.get("member_id") or "",
        )

        return cls(
            room_member=member,
            signing_key_id=_normalize_key_id(payload.get("signing_key_id"), "signing_key_id"),
            encryption_key_id=_normalize_key_id(
                payload.get("encryption_key_id"), "encryption_key_id"
            ),
            public_key_armored=public_key_armored.strip(),
        )

    @property
    def member_id(self) -> str:
        return self.room_member.member_id

    def to_response(self) -> dict:
        return {
            "member_id": self.room_member.member_id,
            "display_name": self.room_member.display_name,
            "signing_fingerprint": self.room_member.signing_fingerprint,
            "encryption_fingerprint": self.room_member.encryption_fingerprint,
            "signing_key_id": self.signing_key_id,
            "encryption_key_id": self.encryption_key_id,
            "public_key_armored": self.public_key_armored,
        }


class ClosedRosterState:
    """Immutable epoch-1 roster state for a simple chat room."""

    def __init__(self, room_id: str):
        self.room_id = _normalize_room_id(room_id)
        self.active_epoch: RoomEpoch | None = None
        self._member_records: Dict[str, ClosedRosterMemberRecord] = {}

    def _serialize_active_epoch(self) -> dict | None:
        if self.active_epoch is None:
            return None

        members: List[dict] = []
        for member in self.active_epoch.members:
            record = self._member_records[member.member_id]
            members.append(record.to_response())

        return {
            "room_id": self.active_epoch.room_id,
            "epoch": self.active_epoch.epoch,
            "immutable_roster": True,
            "roster_hash": self.active_epoch.roster_hash,
            "members": members,
        }

    def serialize(self) -> dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.room_id,
            "active_epoch": self._serialize_active_epoch(),
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
        }

    def bootstrap(self, members: Iterable[dict]) -> dict:
        if self.active_epoch is not None:
            raise ValueError("room roster already initialized")

        records = [ClosedRosterMemberRecord.from_payload(member) for member in members]
        if not records:
            raise ValueError("roster must contain at least one member")

        member_by_id = {record.member_id: record for record in records}
        if len(member_by_id) != len(records):
            raise ValueError("member_id values must be unique within a roster")

        epoch = RoomEpoch(
            room_id=self.room_id,
            epoch=1,
            members=tuple(record.room_member for record in records),
        )

        self.active_epoch = epoch
        self._member_records = member_by_id
        return self.serialize()

    def validate_posted_envelope(self, payload: dict) -> dict:
        if self.active_epoch is None:
            raise ValueError("room roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")

        envelope_type = payload.get("envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError(
                f"unsupported envelope type: expected {OPENPGP_ENVELOPE_TYPE}"
            )

        room_id = _normalize_room_id(payload.get("room_id"))
        if room_id != self.active_epoch.room_id:
            raise ValueError("room_id mismatch")

        try:
            epoch = int(payload.get("epoch"))
        except (TypeError, ValueError):
            raise ValueError("epoch must be an integer") from None
        if epoch != self.active_epoch.epoch:
            raise ValueError("epoch mismatch")

        sender_member_id = payload.get("sender_member_id")
        if not isinstance(sender_member_id, str) or not sender_member_id.strip():
            raise ValueError("sender_member_id must be a non-empty string")
        sender_member_id = sender_member_id.strip()

        sender_record = self._member_records.get(sender_member_id)
        if sender_record is None:
            raise ValueError("sender is not part of the roster")

        sender_signing_fingerprint = normalize_fingerprint(
            payload.get("sender_signing_fingerprint")
        )
        if sender_signing_fingerprint != sender_record.room_member.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        roster_hash = str(payload.get("roster_hash", "")).strip().upper()
        if roster_hash != self.active_epoch.roster_hash:
            raise ValueError("roster hash mismatch")

        recipient_fingerprints = _normalize_fingerprint_list(
            payload.get("recipient_encryption_fingerprints"),
            "recipient_encryption_fingerprints",
        )
        expected_recipient_fingerprints = self.active_epoch.encryption_fingerprints()
        if recipient_fingerprints != expected_recipient_fingerprints:
            raise ValueError("recipient set does not match the room roster")

        intended_recipient_fingerprints = payload.get("intended_recipient_fingerprints")
        if intended_recipient_fingerprints:
            normalized_intended = _normalize_fingerprint_list(
                intended_recipient_fingerprints,
                "intended_recipient_fingerprints",
            )
            if normalized_intended != expected_recipient_fingerprints:
                raise ValueError(
                    "intended recipient fingerprints do not match the room roster"
                )

        recipient_key_ids = _normalize_key_id_list(
            payload.get("recipient_encryption_key_ids"),
            "recipient_encryption_key_ids",
        )
        expected_recipient_key_ids = frozenset(
            self._member_records[member.member_id].encryption_key_id
            for member in self.active_epoch.members
        )
        if recipient_key_ids != expected_recipient_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        if payload.get("anonymous_recipients"):
            raise ValueError("anonymous recipients are forbidden")

        armored_message = payload.get("armored_message")
        if not isinstance(armored_message, str) or not armored_message.strip():
            raise ValueError("armored_message must be a non-empty string")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.active_epoch.room_id,
            "epoch": self.active_epoch.epoch,
            "sender_member_id": sender_member_id,
            "sender_display_name": sender_record.room_member.display_name,
            "sender_signing_fingerprint": sender_record.room_member.signing_fingerprint,
            "roster_hash": self.active_epoch.roster_hash,
            "recipient_encryption_fingerprints": sorted(recipient_fingerprints),
            "intended_recipient_fingerprints": sorted(
                intended_recipient_fingerprints or expected_recipient_fingerprints
            ),
            "recipient_encryption_key_ids": sorted(recipient_key_ids),
            "armored_message": armored_message.strip(),
        }
