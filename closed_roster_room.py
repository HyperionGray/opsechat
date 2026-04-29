"""
Closed-roster OpenPGP room state used by simple chat routes.
"""

from __future__ import annotations

from typing import Dict, List

from openpgp_room_policy import RoomEpoch, RoomMember, normalize_fingerprint


OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"


def _normalize_key_id(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = "".join(ch for ch in value.upper().strip() if ch in "0123456789ABCDEF")
    if len(normalized) < 8:
        raise ValueError(f"{field_name} must be at least 8 hex characters")
    return normalized


class ClosedRosterState:
    """Immutable epoch-1 roster state for alpha simple rooms."""

    def __init__(self, room_id: str):
        self._room_id = str(room_id).strip()
        if not self._room_id:
            raise ValueError("room_id must be non-empty")
        self._active_epoch: Dict | None = None

    def bootstrap(self, members: List[Dict]) -> Dict:
        if self._active_epoch is not None:
            raise ValueError("room roster already initialized")
        if not isinstance(members, list) or not members:
            raise ValueError("members must be a non-empty list")

        prepared: Dict[str, Dict] = {}
        room_members: List[RoomMember] = []
        for member in members:
            if not isinstance(member, dict):
                raise TypeError("member records must be objects")

            member_id = str(member.get("member_id", "")).strip()
            if not member_id:
                raise ValueError("member_id must be non-empty")
            if member_id in prepared:
                raise ValueError("member_id values must be unique within a roster")

            prepared[member_id] = {
                "member_id": member_id,
                "display_name": str(member.get("display_name") or member_id).strip() or member_id,
                "signing_fingerprint": normalize_fingerprint(member.get("signing_fingerprint", "")),
                "encryption_fingerprint": normalize_fingerprint(
                    member.get("encryption_fingerprint", "")
                ),
                "signing_key_id": _normalize_key_id(member.get("signing_key_id", ""), "signing_key_id"),
                "encryption_key_id": _normalize_key_id(
                    member.get("encryption_key_id", ""), "encryption_key_id"
                ),
                "public_key_armored": str(member.get("public_key_armored", "")).strip(),
            }
            if not prepared[member_id]["public_key_armored"]:
                raise ValueError("public_key_armored is required")

            room_members.append(
                RoomMember(
                    member_id=member_id,
                    signing_fingerprint=prepared[member_id]["signing_fingerprint"],
                    encryption_fingerprint=prepared[member_id]["encryption_fingerprint"],
                    display_name=prepared[member_id]["display_name"],
                )
            )

        epoch = RoomEpoch(room_id=self._room_id, epoch=1, members=tuple(room_members))
        canonical_members = []
        for member in epoch.members:
            record = prepared[member.member_id]
            canonical_members.append(
                {
                    "member_id": member.member_id,
                    "display_name": record["display_name"],
                    "signing_fingerprint": member.signing_fingerprint,
                    "encryption_fingerprint": member.encryption_fingerprint,
                    "signing_key_id": record["signing_key_id"],
                    "encryption_key_id": record["encryption_key_id"],
                    "public_key_armored": record["public_key_armored"],
                }
            )

        self._active_epoch = {
            "room_id": epoch.room_id,
            "epoch": epoch.epoch,
            "immutable_roster": True,
            "roster_hash": epoch.roster_hash,
            "members": canonical_members,
        }
        return self.serialize()

    def serialize(self) -> Dict:
        return {
            "mode": OPENPGP_ENVELOPE_TYPE,
            "policy": {
                "immutable_roster": True,
                "shared_room_keys_supported": False,
            },
            "active_epoch": self._active_epoch,
        }

    def validate_posted_envelope(self, payload: Dict) -> Dict:
        if self._active_epoch is None:
            raise ValueError("closed roster not initialized")
        if not isinstance(payload, dict):
            raise TypeError("payload must be an object")

        active_epoch = self._active_epoch
        members_by_id = {member["member_id"]: member for member in active_epoch["members"]}
        expected_fingerprints = {
            member["encryption_fingerprint"].upper() for member in active_epoch["members"]
        }
        expected_key_ids = {member["encryption_key_id"].upper() for member in active_epoch["members"]}

        envelope_type = str(payload.get("envelope_type", "")).strip()
        if envelope_type and envelope_type != OPENPGP_ENVELOPE_TYPE:
            raise ValueError("message type mismatch")

        if str(payload.get("room_id", "")).strip() != active_epoch["room_id"]:
            raise ValueError("room_id mismatch")
        if int(payload.get("epoch", 0)) != int(active_epoch["epoch"]):
            raise ValueError("epoch mismatch")
        if str(payload.get("roster_hash", "")).upper() != str(active_epoch["roster_hash"]).upper():
            raise ValueError("roster hash mismatch")

        sender_member_id = str(payload.get("sender_member_id", "")).strip()
        sender_member = members_by_id.get(sender_member_id)
        if sender_member is None:
            raise ValueError("sender is not part of the roster")

        sender_signing_fingerprint = normalize_fingerprint(payload.get("sender_signing_fingerprint", ""))
        if sender_signing_fingerprint != sender_member["signing_fingerprint"]:
            raise ValueError("sender signing fingerprint mismatch")

        recipient_fingerprints = {
            normalize_fingerprint(fp) for fp in (payload.get("recipient_encryption_fingerprints") or [])
        }
        if recipient_fingerprints != expected_fingerprints:
            raise ValueError("recipient set does not match the room roster")

        # Intended-recipient fingerprints are optional in this alpha path.
        # When present, fail closed and require an exact roster match.
        intended_recipients_raw = payload.get("intended_recipient_fingerprints") or []
        if intended_recipients_raw:
            intended_fingerprints = {normalize_fingerprint(fp) for fp in intended_recipients_raw}
            if intended_fingerprints != expected_fingerprints:
                raise ValueError("intended recipient fingerprints do not match the room roster")
        else:
            intended_fingerprints = set()

        recipient_key_ids = {
            _normalize_key_id(key_id, "recipient_encryption_key_ids")
            for key_id in (payload.get("recipient_encryption_key_ids") or [])
        }
        if recipient_key_ids != expected_key_ids:
            raise ValueError("recipient encryption key ids do not match the room roster")

        armored_message = str(payload.get("armored_message", "")).strip()
        if not armored_message:
            raise ValueError("armored_message is required")

        return {
            "message_type": OPENPGP_ENVELOPE_TYPE,
            "room_id": active_epoch["room_id"],
            "epoch": active_epoch["epoch"],
            "sender_member_id": sender_member_id,
            "sender_display_name": sender_member["display_name"],
            "sender_signing_fingerprint": sender_signing_fingerprint,
            "roster_hash": str(active_epoch["roster_hash"]).upper(),
            "recipient_encryption_fingerprints": sorted(recipient_fingerprints),
            "intended_recipient_fingerprints": sorted(intended_fingerprints),
            "recipient_encryption_key_ids": sorted(recipient_key_ids),
            "armored_message": armored_message,
            # `simple_chat_routes` and existing tests expect `message` in each
            # stored entry; for OpenPGP envelopes that value is the armored body.
            "message": armored_message,
        }
