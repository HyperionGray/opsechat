"""
Closed-roster room state and envelope validation helpers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"
_ROSTER_HASH_DOMAIN = "opsechat-roster-v1"


def _as_non_empty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_member(member: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(member, dict):
        raise TypeError("each member must be an object")

    normalized = {
        "member_id": _as_non_empty_str(member.get("member_id"), "member_id"),
        "display_name": _as_non_empty_str(
            member.get("display_name") or member.get("member_id"),
            "display_name",
        ),
        "signing_fingerprint": _as_non_empty_str(
            member.get("signing_fingerprint"),
            "signing_fingerprint",
        ).upper(),
        "encryption_fingerprint": _as_non_empty_str(
            member.get("encryption_fingerprint"),
            "encryption_fingerprint",
        ).upper(),
        "signing_key_id": _as_non_empty_str(
            member.get("signing_key_id"),
            "signing_key_id",
        ).upper(),
        "encryption_key_id": _as_non_empty_str(
            member.get("encryption_key_id"),
            "encryption_key_id",
        ).upper(),
        "public_key_armored": _as_non_empty_str(
            member.get("public_key_armored"),
            "public_key_armored",
        ),
    }
    return normalized


def _hash_roster(members: Iterable[Dict[str, str]]) -> str:
    lines = sorted(
        f"{m['member_id']}|{m['signing_fingerprint']}|{m['encryption_fingerprint']}"
        for m in members
    )
    payload = _ROSTER_HASH_DOMAIN + "\n" + "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


@dataclass
class ClosedRosterState:
    room_id: str
    _active_epoch: Dict[str, Any] | None = None

    def bootstrap(self, members: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self._active_epoch is not None:
            raise ValueError("room roster is already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        normalized = [_normalize_member(member) for member in members]
        member_ids = [member["member_id"] for member in normalized]
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("member_id values must be unique")

        signing_fps = [member["signing_fingerprint"] for member in normalized]
        if len(signing_fps) != len(set(signing_fps)):
            raise ValueError("signing fingerprints must be unique")

        encryption_fps = [member["encryption_fingerprint"] for member in normalized]
        if len(encryption_fps) != len(set(encryption_fps)):
            raise ValueError("encryption fingerprints must be unique")

        self._active_epoch = {
            "room_id": self.room_id,
            "epoch": 1,
            "immutable_roster": True,
            "roster_hash": _hash_roster(normalized),
            "members": normalized,
        }
        return self.serialize()

    def serialize(self) -> Dict[str, Any]:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self._active_epoch,
        }

    def validate_posted_envelope(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._active_epoch is None:
            raise ValueError("room roster is not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")

        envelope_type = payload.get("envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("invalid envelope type")

        epoch = self._active_epoch
        assert epoch is not None

        room_id = _as_non_empty_str(payload.get("room_id"), "room_id")
        if room_id != epoch["room_id"]:
            raise ValueError("room id mismatch")

        posted_epoch = payload.get("epoch")
        if posted_epoch != epoch["epoch"]:
            raise ValueError("epoch mismatch")

        roster_hash = _as_non_empty_str(payload.get("roster_hash"), "roster_hash")
        if roster_hash != epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        sender_member_id = _as_non_empty_str(
            payload.get("sender_member_id"),
            "sender_member_id",
        )
        sender = next(
            (m for m in epoch["members"] if m["member_id"] == sender_member_id),
            None,
        )
        if sender is None:
            raise ValueError("sender member is not in roster")

        sender_signing_fp = _as_non_empty_str(
            payload.get("sender_signing_fingerprint"),
            "sender_signing_fingerprint",
        ).upper()
        if sender_signing_fp != sender["signing_fingerprint"]:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipient_fps = {
            m["encryption_fingerprint"] for m in epoch["members"]
        }
        expected_recipient_key_ids = {
            m["encryption_key_id"] for m in epoch["members"]
        }

        recipient_fps = payload.get("recipient_encryption_fingerprints")
        if not isinstance(recipient_fps, list):
            raise ValueError("recipient_encryption_fingerprints must be a list")
        normalized_recipient_fps = {
            _as_non_empty_str(v, "recipient").upper()
            for v in recipient_fps
        }
        if normalized_recipient_fps != expected_recipient_fps:
            raise ValueError("recipient set does not match roster")

        intended = payload.get("intended_recipient_fingerprints")
        if not isinstance(intended, list):
            raise ValueError("intended_recipient_fingerprints must be a list")
        normalized_intended = {
            _as_non_empty_str(v, "recipient").upper()
            for v in intended
        }
        if normalized_intended != expected_recipient_fps:
            raise ValueError("recipient set does not match roster")

        recipient_key_ids = payload.get("recipient_encryption_key_ids")
        if not isinstance(recipient_key_ids, list):
            raise ValueError("recipient_encryption_key_ids must be a list")
        normalized_key_ids = {
            _as_non_empty_str(v, "recipient_key_id").upper()
            for v in recipient_key_ids
        }
        if normalized_key_ids != expected_recipient_key_ids:
            raise ValueError("recipient encryption key ids do not match roster")

        armored_message = _as_non_empty_str(
            payload.get("armored_message"),
            "armored_message",
        )

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": room_id,
            "epoch": posted_epoch,
            "sender_member_id": sender_member_id,
            "sender_display_name": sender["display_name"],
            "sender_signing_fingerprint": sender_signing_fp,
            "roster_hash": roster_hash,
            "recipient_encryption_fingerprints": sorted(normalized_recipient_fps),
            "intended_recipient_fingerprints": sorted(normalized_intended),
            "recipient_encryption_key_ids": sorted(normalized_key_ids),
            "armored_message": armored_message,
            "message": armored_message,
        }
