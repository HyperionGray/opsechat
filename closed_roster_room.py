"""
Closed-roster room state and envelope validation helpers.
"""

from __future__ import annotations

from typing import Dict, List

from openpgp_room_policy import RoomEpoch, RoomMember, normalize_fingerprint

OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


class ClosedRosterState:
    """Tracks immutable epoch-1 roster state for a chat room."""

    def __init__(self, room_id: str):
        self._room_id = room_id
        self._active_epoch: RoomEpoch | None = None
        self._member_metadata: Dict[str, Dict[str, str]] = {}

    def bootstrap(self, members: List[dict]) -> dict:
        if self._active_epoch is not None:
            raise ValueError("room roster is already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        room_members = []
        metadata = {}
        for raw in members:
            if not isinstance(raw, dict):
                raise TypeError("each member must be an object")

            member = RoomMember(
                member_id=raw.get("member_id", ""),
                display_name=raw.get("display_name", ""),
                signing_fingerprint=raw.get("signing_fingerprint", ""),
                encryption_fingerprint=raw.get("encryption_fingerprint", ""),
            )
            room_members.append(member)
            metadata[member.member_id] = {
                "signing_key_id": str(raw.get("signing_key_id", "")).strip(),
                "encryption_key_id": str(raw.get("encryption_key_id", "")).strip(),
                "public_key_armored": str(raw.get("public_key_armored", "")).strip(),
            }

        self._active_epoch = RoomEpoch(room_id=self._room_id, epoch=1, members=tuple(room_members))
        self._member_metadata = metadata
        return self.serialize()

    def serialize(self) -> dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self._serialize_epoch(),
        }

    def _serialize_epoch(self) -> dict | None:
        if self._active_epoch is None:
            return None

        members = []
        for member in self._active_epoch.members:
            meta = self._member_metadata.get(member.member_id, {})
            members.append(
                {
                    "member_id": member.member_id,
                    "display_name": member.display_name,
                    "signing_fingerprint": member.signing_fingerprint,
                    "encryption_fingerprint": member.encryption_fingerprint,
                    "signing_key_id": meta.get("signing_key_id", ""),
                    "encryption_key_id": meta.get("encryption_key_id", ""),
                    "public_key_armored": meta.get("public_key_armored", ""),
                }
            )

        return {
            "room_id": self._active_epoch.room_id,
            "epoch": self._active_epoch.epoch,
            "roster_hash": self._active_epoch.roster_hash,
            "immutable_roster": True,
            "members": members,
        }

    def validate_posted_envelope(self, payload: dict) -> dict:
        if self._active_epoch is None:
            raise ValueError("room roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")

        epoch = self._active_epoch
        if payload.get("envelope_type") != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("unsupported envelope type")
        if payload.get("room_id") != epoch.room_id:
            raise ValueError("room_id mismatch")
        if payload.get("epoch") != epoch.epoch:
            raise ValueError("epoch mismatch")
        if payload.get("roster_hash") != epoch.roster_hash:
            raise ValueError("roster hash mismatch")

        sender_member_id = str(payload.get("sender_member_id", "")).strip()
        member_by_id = {member.member_id: member for member in epoch.members}
        sender_member = member_by_id.get(sender_member_id)
        if sender_member is None:
            raise ValueError("sender member is not part of the room roster")

        sender_fp = normalize_fingerprint(str(payload.get("sender_signing_fingerprint", "")))
        if sender_fp != sender_member.signing_fingerprint:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipients = epoch.encryption_fingerprints()
        recipient_fps = {
            normalize_fingerprint(value)
            for value in payload.get("recipient_encryption_fingerprints", [])
        }
        if recipient_fps != expected_recipients:
            raise ValueError("recipient set does not match the room roster")

        intended_fps = {
            normalize_fingerprint(value)
            for value in payload.get("intended_recipient_fingerprints", [])
        }
        if intended_fps and intended_fps != expected_recipients:
            raise ValueError("intended recipient fingerprints do not match the room roster")

        expected_key_ids = {
            self._member_metadata[member.member_id].get("encryption_key_id", "")
            for member in epoch.members
        }
        recipient_key_ids = {
            str(value).strip() for value in payload.get("recipient_encryption_key_ids", [])
        }
        if recipient_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        armored_message = payload.get("armored_message")
        if not isinstance(armored_message, str) or not armored_message.strip():
            raise ValueError("armored_message is required")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": epoch.room_id,
            "epoch": epoch.epoch,
            "sender_member_id": sender_member.member_id,
            "sender_display_name": sender_member.display_name,
            "sender_signing_fingerprint": sender_member.signing_fingerprint,
            "roster_hash": epoch.roster_hash,
            "recipient_encryption_fingerprints": sorted(recipient_fps),
            "intended_recipient_fingerprints": sorted(intended_fps or recipient_fps),
            "recipient_encryption_key_ids": sorted(recipient_key_ids),
            "armored_message": armored_message,
        }
