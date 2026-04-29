"""Closed-roster room state helpers used by simple chat routes."""

from __future__ import annotations

from typing import Dict, List

from openpgp_room_policy import RoomEpoch, RoomMember, normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


class ClosedRosterState:
    """In-memory immutable epoch-1 roster state for a room."""

    def __init__(self, room_id: str):
        self.room_id = str(room_id).strip()
        if not self.room_id:
            raise ValueError("room_id must be non-empty")

        self._active_epoch: RoomEpoch | None = None
        self._member_meta: Dict[str, dict] = {}

    def bootstrap(self, members: List[dict]) -> dict:
        if self._active_epoch is not None:
            raise ValueError("room roster is already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        roster_members: list[RoomMember] = []
        member_meta: Dict[str, dict] = {}

        for raw in members:
            if not isinstance(raw, dict):
                raise TypeError("each member must be an object")

            member_id = str(raw.get("member_id", "")).strip()
            signing_fingerprint = str(raw.get("signing_fingerprint", "")).strip()
            encryption_fingerprint = str(raw.get("encryption_fingerprint", "")).strip()
            display_name = str(raw.get("display_name", member_id)).strip() or member_id
            signing_key_id = str(raw.get("signing_key_id", "")).strip()
            encryption_key_id = str(raw.get("encryption_key_id", "")).strip()
            public_key_armored = str(raw.get("public_key_armored", "")).strip()

            if not member_id:
                raise ValueError("member_id must be non-empty")
            if not signing_key_id or not encryption_key_id:
                raise ValueError("member key ids must be provided")
            if not public_key_armored:
                raise ValueError("public_key_armored must be provided")

            member = RoomMember(
                member_id=member_id,
                signing_fingerprint=signing_fingerprint,
                encryption_fingerprint=encryption_fingerprint,
                display_name=display_name,
            )
            roster_members.append(member)
            member_meta[member.member_id] = {
                "display_name": display_name,
                "signing_key_id": signing_key_id.upper(),
                "encryption_key_id": encryption_key_id.upper(),
                "public_key_armored": public_key_armored,
            }

        self._active_epoch = RoomEpoch(room_id=self.room_id, epoch=1, members=tuple(roster_members))
        self._member_meta = member_meta
        return self.serialize()

    def serialize(self) -> dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self._serialize_epoch(self._active_epoch),
        }

    def validate_posted_envelope(self, payload: dict) -> dict:
        if self._active_epoch is None:
            raise ValueError("room roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")

        envelope_type = str(payload.get("envelope_type", "")).strip()
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("unsupported envelope type")

        epoch = self._active_epoch

        room_id = str(payload.get("room_id", "")).strip()
        if room_id != epoch.room_id:
            raise ValueError("room_id mismatch")

        try:
            posted_epoch = int(payload.get("epoch"))
        except (TypeError, ValueError):
            raise ValueError("epoch must be an integer")
        if posted_epoch != epoch.epoch:
            raise ValueError("epoch mismatch")

        roster_hash = str(payload.get("roster_hash", "")).strip().upper()
        if roster_hash != epoch.roster_hash:
            raise ValueError("roster hash mismatch")

        sender_member_id = str(payload.get("sender_member_id", "")).strip()
        sender = next((member for member in epoch.members if member.member_id == sender_member_id), None)
        if sender is None:
            raise ValueError("sender is not part of the roster")

        sender_signing_fingerprint = normalize_fingerprint(
            str(payload.get("sender_signing_fingerprint", "")).strip()
        )
        if sender_signing_fingerprint != sender.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        recipient_fps = self._normalized_set(payload.get("recipient_encryption_fingerprints"))
        expected_recipients = epoch.encryption_fingerprints()
        if recipient_fps != expected_recipients:
            raise ValueError("recipient set does not match the room roster")

        intended_fps = self._normalized_optional_set(
            payload.get("intended_recipient_fingerprints"),
            "intended_recipient_fingerprints",
        )
        if intended_fps is not None and intended_fps != expected_recipients:
            raise ValueError("intended recipient fingerprints do not match the room roster")

        recipient_key_ids = self._normalized_keyid_set(payload.get("recipient_encryption_key_ids"))
        expected_key_ids = {
            self._member_meta[member.member_id]["encryption_key_id"]
            for member in epoch.members
        }
        if recipient_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        armored_message = str(payload.get("armored_message", "")).strip()
        if not armored_message:
            raise ValueError("armored_message is required")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "envelope_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": epoch.room_id,
            "epoch": epoch.epoch,
            "sender_member_id": sender.member_id,
            "sender_display_name": self._member_meta[sender.member_id]["display_name"],
            "sender_signing_fingerprint": sender.signing_fingerprint,
            "roster_hash": epoch.roster_hash,
            "recipient_encryption_fingerprints": sorted(recipient_fps),
            "intended_recipient_fingerprints": sorted(
                intended_fps if intended_fps is not None else expected_recipients
            ),
            "recipient_encryption_key_ids": sorted(recipient_key_ids),
            "armored_message": armored_message,
        }

    def _serialize_epoch(self, epoch: RoomEpoch | None) -> dict | None:
        if epoch is None:
            return None

        members = []
        for member in epoch.members:
            meta = self._member_meta[member.member_id]
            members.append(
                {
                    "member_id": member.member_id,
                    "display_name": meta["display_name"],
                    "signing_fingerprint": member.signing_fingerprint,
                    "encryption_fingerprint": member.encryption_fingerprint,
                    "signing_key_id": meta["signing_key_id"],
                    "encryption_key_id": meta["encryption_key_id"],
                    "public_key_armored": meta["public_key_armored"],
                }
            )

        return {
            "room_id": epoch.room_id,
            "epoch": epoch.epoch,
            "roster_hash": epoch.roster_hash,
            "immutable_roster": True,
            "members": members,
        }

    @staticmethod
    def _normalized_set(value) -> set[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("recipient_encryption_fingerprints must be a non-empty list")
        return {normalize_fingerprint(str(item)) for item in value}

    @staticmethod
    def _normalized_optional_set(value, field_name: str) -> set[str] | None:
        if value is None:
            return None
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field_name} must be a non-empty list when provided")
        return {normalize_fingerprint(str(item)) for item in value}

    @staticmethod
    def _normalized_keyid_set(value) -> set[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("recipient_encryption_key_ids must be a non-empty list")
        normalized = {str(item).strip().upper() for item in value if str(item).strip()}
        if not normalized:
            raise ValueError("recipient_encryption_key_ids must be a non-empty list")
        return normalized
