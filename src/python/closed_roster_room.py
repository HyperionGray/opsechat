"""
Closed-roster OpenPGP room state helpers.

This module keeps the server-side room metadata small and deterministic. It
tracks an immutable epoch-1 roster, exposes a JSON representation for the web
client, and validates the outer metadata attached to posted OpenPGP envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from openpgp_room_policy import RoomEpoch, RoomMember, normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"

_HEX_RE = re.compile(r"[^0-9A-F]")


def _normalize_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _normalize_key_id(value: Any, field_name: str) -> str:
    normalized = _normalize_text(value, field_name).upper()
    normalized = _HEX_RE.sub("", normalized)
    if len(normalized) < 8:
        raise ValueError(f"{field_name} must contain at least 8 hex characters")
    return normalized


@dataclass(frozen=True)
class ClosedRosterMember:
    member_id: str
    display_name: str
    signing_fingerprint: str
    encryption_fingerprint: str
    signing_key_id: str
    encryption_key_id: str
    public_key_armored: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ClosedRosterMember":
        if not isinstance(payload, dict):
            raise TypeError("roster member must be a JSON object")

        member_id = _normalize_text(payload.get("member_id"), "member_id")
        display_name = _normalize_text(
            payload.get("display_name", member_id),
            "display_name",
        )
        signing_fingerprint = normalize_fingerprint(payload.get("signing_fingerprint"))
        encryption_fingerprint = normalize_fingerprint(payload.get("encryption_fingerprint"))
        signing_key_id = _normalize_key_id(payload.get("signing_key_id"), "signing_key_id")
        encryption_key_id = _normalize_key_id(
            payload.get("encryption_key_id"),
            "encryption_key_id",
        )
        public_key_armored = _normalize_text(
            payload.get("public_key_armored"),
            "public_key_armored",
        )

        return cls(
            member_id=member_id,
            display_name=display_name,
            signing_fingerprint=signing_fingerprint,
            encryption_fingerprint=encryption_fingerprint,
            signing_key_id=signing_key_id,
            encryption_key_id=encryption_key_id,
            public_key_armored=public_key_armored,
        )

    def to_room_member(self) -> RoomMember:
        return RoomMember(
            member_id=self.member_id,
            display_name=self.display_name,
            signing_fingerprint=self.signing_fingerprint,
            encryption_fingerprint=self.encryption_fingerprint,
        )

    def serialize(self) -> dict[str, str]:
        return {
            "member_id": self.member_id,
            "display_name": self.display_name,
            "signing_fingerprint": self.signing_fingerprint,
            "encryption_fingerprint": self.encryption_fingerprint,
            "signing_key_id": self.signing_key_id,
            "encryption_key_id": self.encryption_key_id,
            "public_key_armored": self.public_key_armored,
        }


class ClosedRosterState:
    """Immutable epoch-1 room roster with envelope metadata validation."""

    def __init__(self, room_id: str):
        self.room_id = _normalize_text(room_id, "room_id")
        self._active_epoch: RoomEpoch | None = None
        self._members_by_id: dict[str, ClosedRosterMember] = {}

    def bootstrap(self, members: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, Any]:
        if self._active_epoch is not None:
            raise ValueError("room roster already initialized")

        normalized_members = [ClosedRosterMember.from_payload(member) for member in members]
        epoch = RoomEpoch(
            room_id=self.room_id,
            epoch=1,
            members=tuple(member.to_room_member() for member in normalized_members),
        )

        ordered_members: list[ClosedRosterMember] = []
        for room_member in epoch.members:
            source = next(
                member
                for member in normalized_members
                if member.member_id == room_member.member_id
                and member.signing_fingerprint == room_member.signing_fingerprint
                and member.encryption_fingerprint == room_member.encryption_fingerprint
            )
            ordered_members.append(source)

        self._active_epoch = epoch
        self._members_by_id = {member.member_id: member for member in ordered_members}
        return self.serialize()

    def serialize(self) -> dict[str, Any]:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self._serialize_active_epoch(),
        }

    def validate_posted_envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._active_epoch is None:
            raise ValueError("room roster not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be a JSON object")

        envelope_type = _normalize_text(payload.get("envelope_type"), "envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("envelope_type mismatch")

        room_id = _normalize_text(payload.get("room_id"), "room_id")
        if room_id != self._active_epoch.room_id:
            raise ValueError("room_id mismatch")

        epoch_value = payload.get("epoch")
        try:
            epoch_number = int(epoch_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("epoch must be an integer") from exc
        if epoch_number != self._active_epoch.epoch:
            raise ValueError("epoch mismatch")

        sender_member_id = _normalize_text(payload.get("sender_member_id"), "sender_member_id")
        sender = self._members_by_id.get(sender_member_id)
        if sender is None:
            raise ValueError("sender is not part of the room roster")

        sender_signing_fingerprint = normalize_fingerprint(payload.get("sender_signing_fingerprint"))
        if sender_signing_fingerprint != sender.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        roster_hash = _normalize_text(payload.get("roster_hash"), "roster_hash").upper()
        if roster_hash != self._active_epoch.roster_hash:
            raise ValueError("roster hash mismatch")

        armored_message = _normalize_text(payload.get("armored_message"), "armored_message")

        expected_fingerprints = {
            member.encryption_fingerprint for member in self._members_by_id.values()
        }
        recipient_fingerprints = {
            normalize_fingerprint(fingerprint)
            for fingerprint in (payload.get("recipient_encryption_fingerprints") or [])
        }
        if recipient_fingerprints != expected_fingerprints:
            raise ValueError("recipient set does not match the room roster")

        intended = payload.get("intended_recipient_fingerprints") or []
        intended_fingerprints = {
            normalize_fingerprint(fingerprint)
            for fingerprint in intended
        }
        if intended_fingerprints and intended_fingerprints != expected_fingerprints:
            raise ValueError("intended recipient fingerprints do not match the room roster")

        expected_key_ids = {
            member.encryption_key_id for member in self._members_by_id.values()
        }
        recipient_key_ids = {
            _normalize_key_id(key_id, "recipient_encryption_key_ids")
            for key_id in payload.get("recipient_encryption_key_ids", [])
        }
        if recipient_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "message": armored_message,
            "armored_message": armored_message,
            "sender_member_id": sender.member_id,
            "sender_display_name": sender.display_name,
            "sender_signing_fingerprint": sender.signing_fingerprint,
            "epoch": self._active_epoch.epoch,
            "roster_hash": self._active_epoch.roster_hash,
            "recipient_encryption_fingerprints": sorted(expected_fingerprints),
            "recipient_encryption_key_ids": sorted(expected_key_ids),
        }

    def _serialize_active_epoch(self) -> dict[str, Any] | None:
        if self._active_epoch is None:
            return None

        members = []
        for room_member in self._active_epoch.members:
            member = self._members_by_id[room_member.member_id]
            members.append(member.serialize())

        return {
            "room_id": self._active_epoch.room_id,
            "epoch": self._active_epoch.epoch,
            "roster_hash": self._active_epoch.roster_hash,
            "immutable_roster": True,
            "members": members,
        }
