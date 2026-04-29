"""Closed-roster room state and envelope validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

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

    def to_epoch_json(self) -> dict:
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
    """In-memory closed-roster state for a single room."""

    def __init__(self, room_id: str):
        self.room_id = str(room_id)
        self._active_epoch: dict | None = None
        self._policy = {
            "immutable_roster": True,
            "shared_room_keys_supported": False,
        }

    def serialize(self) -> dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": dict(self._policy),
            "active_epoch": self._active_epoch,
        }

    def bootstrap(self, members_payload: object) -> dict:
        if self._active_epoch is not None:
            raise ValueError("closed roster already initialized")
        if not isinstance(members_payload, list) or not members_payload:
            raise ValueError("members must be a non-empty list")

        members = self._parse_members(members_payload)
        roster_hash = hash_roster(
            RoomMember(
                member_id=member.member_id,
                signing_fingerprint=member.signing_fingerprint,
                encryption_fingerprint=member.encryption_fingerprint,
                display_name=member.display_name,
            )
            for member in members
        )

        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": roster_hash,
            "members": [member.to_epoch_json() for member in members],
        }
        return self.serialize()

    def validate_posted_envelope(self, payload: object) -> dict:
        if self._active_epoch is None:
            raise ValueError("closed roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be a JSON object")

        envelope_type = str(payload.get("envelope_type", "")).strip()
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("invalid envelope_type")

        room_id = str(payload.get("room_id", "")).strip()
        if room_id != self.room_id:
            raise ValueError("room id mismatch")

        epoch = payload.get("epoch")
        if epoch != self._active_epoch["epoch"]:
            raise ValueError("epoch mismatch")

        roster_hash = str(payload.get("roster_hash", "")).strip().upper()
        if roster_hash != self._active_epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        sender_member_id = str(payload.get("sender_member_id", "")).strip()
        sender = self._member_by_id().get(sender_member_id)
        if sender is None:
            raise ValueError("sender is not part of the roster")

        sender_fp = normalize_fingerprint(str(payload.get("sender_signing_fingerprint", "")))
        if sender_fp != sender["signing_fingerprint"]:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipients = {
            member["encryption_fingerprint"] for member in self._active_epoch["members"]
        }
        recipient_fps = {
            normalize_fingerprint(value)
            for value in payload.get("recipient_encryption_fingerprints") or []
        }
        if recipient_fps != expected_recipients:
            raise ValueError("recipient set does not match the room roster")

        intended_fps_raw = payload.get("intended_recipient_fingerprints")
        if intended_fps_raw is not None:
            intended_fps = {normalize_fingerprint(value) for value in intended_fps_raw}
            if intended_fps != expected_recipients:
                raise ValueError("intended recipient fingerprints do not match the room roster")

        expected_key_ids = {
            member["encryption_key_id"] for member in self._active_epoch["members"]
        }
        provided_key_ids = {
            str(value).strip().upper()
            for value in (payload.get("recipient_encryption_key_ids") or [])
            if str(value).strip()
        }
        if provided_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        armored_message = payload.get("armored_message")
        if not isinstance(armored_message, str) or not armored_message.strip():
            raise ValueError("armored_message is required")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "message": armored_message,
            "armored_message": armored_message,
            "sender_member_id": sender_member_id,
            "sender_display_name": sender["display_name"],
            "sender_signing_fingerprint": sender_fp,
            "epoch": self._active_epoch["epoch"],
            "roster_hash": self._active_epoch["roster_hash"],
        }

    def _member_by_id(self) -> Dict[str, dict]:
        return {member["member_id"]: member for member in self._active_epoch["members"]}

    @staticmethod
    def _parse_members(members_payload: List[object]) -> List[_RosterMember]:
        parsed: List[_RosterMember] = []
        seen_ids = set()

        for index, raw in enumerate(members_payload, start=1):
            if not isinstance(raw, dict):
                raise TypeError(f"members[{index}] must be an object")

            member_id = str(raw.get("member_id", "")).strip()
            if not member_id:
                raise ValueError(f"members[{index}].member_id is required")
            if member_id in seen_ids:
                raise ValueError("member_id values must be unique")
            seen_ids.add(member_id)

            display_name = str(raw.get("display_name") or member_id).strip() or member_id
            signing_fingerprint = normalize_fingerprint(raw.get("signing_fingerprint"))
            encryption_fingerprint = normalize_fingerprint(raw.get("encryption_fingerprint"))
            signing_key_id = str(raw.get("signing_key_id", "")).strip().upper()
            encryption_key_id = str(raw.get("encryption_key_id", "")).strip().upper()
            public_key_armored = str(raw.get("public_key_armored", "")).strip()

            if not signing_key_id or not encryption_key_id:
                raise ValueError("member key ids are required")
            if not public_key_armored:
                raise ValueError("public_key_armored is required")

            parsed.append(
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

        return parsed
