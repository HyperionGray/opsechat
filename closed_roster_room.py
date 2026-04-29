"""
Closed-roster OpenPGP room state validation helpers.

This module keeps room membership immutable after epoch-1 bootstrap and validates
posted OpenPGP envelope metadata against the initialized roster.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List


OPENPGP_ENVELOPE_TYPE = "closed-roster-openpgp-v1"
ROSTER_HASH_DOMAIN = "opsechat-roster-v1"


class ClosedRosterState:
    """Track immutable epoch-1 room roster and validate posted envelopes."""

    def __init__(self, room_id: str):
        self.room_id = room_id
        self._active_epoch: Dict[str, Any] | None = None

    def bootstrap(self, members: List[Dict]) -> Dict:
        if self._active_epoch is not None:
            raise ValueError("Room roster already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("No roster members provided")

        normalized_members: List[Dict] = []
        seen_member_ids = set()
        seen_signing_fps = set()
        seen_encryption_fps = set()
        seen_encryption_key_ids = set()

        for member in members:
            if not isinstance(member, dict):
                raise TypeError("roster members must be objects")

            member_id = str(member.get("member_id", "")).strip()
            if not member_id:
                raise ValueError("member_id is required for every roster member")
            if member_id in seen_member_ids:
                raise ValueError("member_id values must be unique within the roster")

            signing_fp = self._normalize_hex(member.get("signing_fingerprint"), "signing_fingerprint")
            encryption_fp = self._normalize_hex(
                member.get("encryption_fingerprint"),
                "encryption_fingerprint",
            )
            signing_key_id = self._normalize_hex(member.get("signing_key_id"), "signing_key_id", lengths=(16,))
            encryption_key_id = self._normalize_hex(
                member.get("encryption_key_id"),
                "encryption_key_id",
                lengths=(16,),
            )
            public_key_armored = str(member.get("public_key_armored", "")).strip()
            if not public_key_armored:
                raise ValueError("public_key_armored is required for every roster member")
            display_name = str(member.get("display_name", "")).strip() or member_id

            if signing_fp in seen_signing_fps:
                raise ValueError("signing fingerprints must be unique within the roster")
            if encryption_fp in seen_encryption_fps:
                raise ValueError("encryption fingerprints must be unique within the roster")
            if encryption_key_id in seen_encryption_key_ids:
                raise ValueError("encryption key ids must be unique within the roster")

            seen_member_ids.add(member_id)
            seen_signing_fps.add(signing_fp)
            seen_encryption_fps.add(encryption_fp)
            seen_encryption_key_ids.add(encryption_key_id)

            normalized_members.append(
                {
                    "member_id": member_id,
                    "display_name": display_name,
                    "signing_fingerprint": signing_fp,
                    "encryption_fingerprint": encryption_fp,
                    "signing_key_id": signing_key_id,
                    "encryption_key_id": encryption_key_id,
                    "public_key_armored": public_key_armored,
                }
            )

        normalized_members.sort(key=lambda m: m["member_id"])
        roster_hash = self._hash_roster(normalized_members)
        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": roster_hash,
            "members": normalized_members,
        }
        return self.serialize()

    def serialize(self) -> Dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "active_epoch": self._active_epoch,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
        }

    def validate_posted_envelope(self, payload: Dict) -> Dict:
        if self._active_epoch is None:
            raise ValueError("Room roster not initialized")
        if not isinstance(payload, dict):
            raise TypeError("Envelope payload must be an object")

        envelope_type = payload.get("envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("Unsupported envelope_type")

        sender_member_id = str(payload.get("sender_member_id", "")).strip()
        sender_signing_fp = self._normalize_hex(payload.get("sender_signing_fingerprint"), "sender_signing_fingerprint")
        armored_message = str(payload.get("armored_message", "")).strip()
        if not armored_message:
            raise ValueError("armored_message is required")

        members = self._active_epoch["members"]
        by_member_id = {member["member_id"]: member for member in members}
        sender = by_member_id.get(sender_member_id)
        if sender is None:
            raise ValueError("sender member is not in the active roster")
        if sender["signing_fingerprint"] != sender_signing_fp:
            raise ValueError("sender signing fingerprint mismatch")

        expected_roster_hash = self._active_epoch["roster_hash"]
        if str(payload.get("roster_hash", "")).strip().upper() != expected_roster_hash:
            raise ValueError("roster hash mismatch")

        expected_recipient_fps = sorted(member["encryption_fingerprint"] for member in members)
        recipient_fingerprints = sorted(
            self._normalize_hex(fingerprint_value, "recipient_encryption_fingerprint")
            for fingerprint_value in payload.get("recipient_encryption_fingerprints", [])
        )
        intended_fingerprints = sorted(
            self._normalize_hex(fingerprint_value, "intended_recipient_fingerprint")
            for fingerprint_value in payload.get("intended_recipient_fingerprints", [])
        )
        if (
            recipient_fingerprints != expected_recipient_fps
            or intended_fingerprints != expected_recipient_fps
        ):
            raise ValueError("recipient set does not match active roster")

        expected_recipient_key_ids = sorted(member["encryption_key_id"] for member in members)
        recipient_key_ids = sorted(
            self._normalize_hex(value, "recipient_encryption_key_id", lengths=(16,))
            for value in payload.get("recipient_encryption_key_ids", [])
        )
        if recipient_key_ids != expected_recipient_key_ids:
            raise ValueError("recipient encryption key ids do not match active roster")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "envelope_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.room_id,
            "epoch": self._active_epoch["epoch"],
            "sender_member_id": sender["member_id"],
            "sender_display_name": sender["display_name"],
            "sender_signing_fingerprint": sender["signing_fingerprint"],
            "roster_hash": expected_roster_hash,
            "recipient_encryption_fingerprints": expected_recipient_fps,
            "recipient_encryption_key_ids": expected_recipient_key_ids,
            "armored_message": armored_message,
        }

    @staticmethod
    def _normalize_hex(
        fingerprint_value: str | None, field_name: str, lengths=(40, 64)
    ) -> str:
        normalized = "".join(
            ch for ch in str(fingerprint_value or "").upper() if ch in "0123456789ABCDEF"
        )
        if len(normalized) not in lengths:
            if len(lengths) == 1:
                raise ValueError(f"{field_name} must be {lengths[0]} hex characters")
            raise ValueError(f"{field_name} must be 40 or 64 hex characters")
        return normalized

    @staticmethod
    def _hash_roster(members: List[Dict]) -> str:
        digest = hashlib.sha256()
        digest.update(f"{ROSTER_HASH_DOMAIN}\n".encode("utf-8"))
        for member in members:
            digest.update(
                (
                    f"{member['member_id']}|"
                    f"{member['signing_fingerprint']}|"
                    f"{member['encryption_fingerprint']}|"
                    f"{member['encryption_key_id']}\n"
                ).encode("utf-8")
            )
        return digest.hexdigest().upper()
