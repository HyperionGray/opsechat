"""
Closed-roster room compatibility helpers used by simple_chat_routes.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Set


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


def _normalize_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must be non-empty")
    return normalized


def _normalize_fingerprint(value: str, field: str) -> str:
    normalized = _normalize_text(value, field).upper().replace(" ", "").replace(":", "")
    if len(normalized) not in {40, 64}:
        raise ValueError(f"{field} must be 40 or 64 hex characters")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hex") from exc
    return normalized


def _normalize_fingerprint_set(values: Iterable[str], field: str) -> Set[str]:
    if not isinstance(values, (list, tuple, set)):
        raise TypeError(f"{field} must be a list")
    return {_normalize_fingerprint(item, field) for item in values}


def _roster_hash(room_id: str, epoch: int, members: List[Dict[str, str]]) -> str:
    """
    Build a deterministic room roster hash.

    Canonical format:
    - Domain prefix: ``opsechat-room-state-v1``
    - Room identity: ``room_id``
    - Epoch number
    - Canonical member lines sorted by ``(member_id, signing_fingerprint)``
      where each line is ``member_id|signing_fingerprint|encryption_fingerprint``.

    The domain/version prefix allows future hash format changes without
    ambiguity.
    """
    canonical_lines = [
        f"{member['member_id']}|{member['signing_fingerprint']}|{member['encryption_fingerprint']}"
        for member in sorted(members, key=lambda m: (m["member_id"], m["signing_fingerprint"]))
    ]
    payload = f"opsechat-room-state-v1|{room_id}|{epoch}|" + "|".join(canonical_lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


class ClosedRosterState:
    """
    Minimal immutable epoch-1 closed-roster state holder.
    """

    def __init__(self, room_id: str):
        self.room_id = _normalize_text(room_id, "room_id")
        self.active_epoch = None

    def serialize(self) -> dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self.active_epoch,
        }

    def bootstrap(self, members: List[dict]) -> dict:
        """
        Initialize immutable epoch-1 roster state.

        Expected member object fields:
        - required: ``member_id``, ``signing_fingerprint``,
          ``encryption_fingerprint``, ``public_key_armored``
        - optional (derived when absent): ``display_name``, ``signing_key_id``,
          ``encryption_key_id``

        Fingerprints must be unique and valid hex (40 or 64 chars after
        normalization). ``public_key_armored`` must be a non-empty string
        containing the member's ASCII-armored public key block.
        """
        if self.active_epoch is not None:
            raise ValueError("room roster already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        normalized_members: List[Dict[str, str]] = []
        member_ids = set()
        signing_fps = set()
        encryption_fps = set()
        encryption_key_ids = set()

        for raw in members:
            if not isinstance(raw, dict):
                raise TypeError("each roster member must be an object")
            member_id = _normalize_text(raw.get("member_id"), "member_id")
            if member_id in member_ids:
                raise ValueError("member_id values must be unique")
            member_ids.add(member_id)

            signing_fp = _normalize_fingerprint(
                raw.get("signing_fingerprint"), "signing_fingerprint"
            )
            if signing_fp in signing_fps:
                raise ValueError("signing fingerprints must be unique")
            signing_fps.add(signing_fp)

            encryption_fp = _normalize_fingerprint(
                raw.get("encryption_fingerprint"), "encryption_fingerprint"
            )
            if encryption_fp in encryption_fps:
                raise ValueError("encryption fingerprints must be unique")
            encryption_fps.add(encryption_fp)

            encryption_key_id = _normalize_text(
                raw.get("encryption_key_id") or encryption_fp[:16],
                "encryption_key_id",
            )
            if encryption_key_id in encryption_key_ids:
                raise ValueError("encryption key ids must be unique")
            encryption_key_ids.add(encryption_key_id)

            normalized_members.append(
                {
                    "member_id": member_id,
                    "display_name": _normalize_text(
                        raw.get("display_name") or member_id, "display_name"
                    ),
                    "signing_fingerprint": signing_fp,
                    "encryption_fingerprint": encryption_fp,
                    "signing_key_id": _normalize_text(
                        raw.get("signing_key_id") or signing_fp[:16], "signing_key_id"
                    ),
                    "encryption_key_id": encryption_key_id,
                    "public_key_armored": _normalize_text(
                        raw.get("public_key_armored"),
                        "public_key_armored",
                    ),
                }
            )

        epoch = 1
        self.active_epoch = {
            "room_id": self.room_id,
            "epoch": epoch,
            "immutable_roster": True,
            "roster_hash": _roster_hash(self.room_id, epoch, normalized_members),
            "members": normalized_members,
        }
        return self.serialize()

    def validate_posted_envelope(self, payload: dict) -> dict:
        if self.active_epoch is None:
            raise ValueError("room roster not initialized")
        if not isinstance(payload, dict):
            raise TypeError("message payload must be an object")

        envelope_type = _normalize_text(payload.get("envelope_type"), "envelope_type")
        if envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("unsupported envelope type")

        if _normalize_text(payload.get("room_id"), "room_id") != self.active_epoch["room_id"]:
            raise ValueError("room_id mismatch")
        if int(payload.get("epoch")) != int(self.active_epoch["epoch"]):
            raise ValueError("epoch mismatch")
        if _normalize_text(payload.get("roster_hash"), "roster_hash") != self.active_epoch["roster_hash"]:
            raise ValueError("roster hash mismatch")

        sender_member_id = _normalize_text(payload.get("sender_member_id"), "sender_member_id")
        member_by_id = {
            member["member_id"]: member for member in self.active_epoch["members"]
        }
        sender = member_by_id.get(sender_member_id)
        if sender is None:
            raise ValueError("sender is not part of the roster")

        sender_signing_fp = _normalize_fingerprint(
            payload.get("sender_signing_fingerprint"), "sender_signing_fingerprint"
        )
        if sender_signing_fp != sender["signing_fingerprint"]:
            raise ValueError("sender signing fingerprint mismatch")

        expected_recipients = {
            member["encryption_fingerprint"] for member in self.active_epoch["members"]
        }
        recipients = _normalize_fingerprint_set(
            payload.get("recipient_encryption_fingerprints", []),
            "recipient_encryption_fingerprints",
        )
        if recipients != expected_recipients:
            raise ValueError("recipient set does not match the room roster")

        intended = _normalize_fingerprint_set(
            payload.get("intended_recipient_fingerprints", []),
            "intended_recipient_fingerprints",
        )
        if intended and intended != expected_recipients:
            raise ValueError("intended recipient fingerprints do not match the room roster")

        expected_key_ids = {
            member["encryption_key_id"] for member in self.active_epoch["members"]
        }
        if payload.get("recipient_encryption_key_ids") is not None:
            if not isinstance(payload.get("recipient_encryption_key_ids"), (list, tuple, set)):
                raise TypeError("recipient_encryption_key_ids must be a list")
            provided_key_ids = {
                _normalize_text(value, "recipient_encryption_key_ids")
                for value in payload.get("recipient_encryption_key_ids")
            }
            if provided_key_ids != expected_key_ids:
                raise ValueError("recipient encryption key ids do not match")

        armored_message = _normalize_text(payload.get("armored_message"), "armored_message")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "envelope_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": self.active_epoch["room_id"],
            "epoch": self.active_epoch["epoch"],
            "sender_member_id": sender_member_id,
            "sender_display_name": sender["display_name"],
            "sender_signing_fingerprint": sender_signing_fp,
            "roster_hash": self.active_epoch["roster_hash"],
            "recipient_encryption_fingerprints": sorted(expected_recipients),
            "intended_recipient_fingerprints": sorted(intended or expected_recipients),
            "recipient_encryption_key_ids": sorted(expected_key_ids),
            "armored_message": armored_message,
            "message": armored_message,
        }
