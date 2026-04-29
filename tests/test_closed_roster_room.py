import hashlib

import pytest

from closed_roster_room import ClosedRosterState, OPENPGP_ENVELOPE_TYPE


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()


def _member(member_id: str) -> dict:
    return {
        "member_id": member_id,
        "display_name": member_id.title(),
        "signing_fingerprint": _fp(f"{member_id}-sign"),
        "encryption_fingerprint": _fp(f"{member_id}-enc"),
        "signing_key_id": _fp(f"{member_id}-sign-key")[:16],
        "encryption_key_id": _fp(f"{member_id}-enc-key")[:16],
        "public_key_armored": f"-----BEGIN PGP PUBLIC KEY BLOCK-----\n{member_id}\n-----END PGP PUBLIC KEY BLOCK-----",
    }


def _payload(state: dict, sender_member_id: str = "alice") -> dict:
    epoch = state["active_epoch"]
    sender = next(m for m in epoch["members"] if m["member_id"] == sender_member_id)
    return {
        "envelope_type": OPENPGP_ENVELOPE_TYPE,
        "room_id": epoch["room_id"],
        "epoch": epoch["epoch"],
        "sender_member_id": sender["member_id"],
        "sender_signing_fingerprint": sender["signing_fingerprint"],
        "roster_hash": epoch["roster_hash"],
        "recipient_encryption_fingerprints": [
            m["encryption_fingerprint"] for m in epoch["members"]
        ],
        "intended_recipient_fingerprints": [
            m["encryption_fingerprint"] for m in epoch["members"]
        ],
        "recipient_encryption_key_ids": [m["encryption_key_id"] for m in epoch["members"]],
        "armored_message": "-----BEGIN PGP MESSAGE-----\nopaque\n-----END PGP MESSAGE-----",
    }


def test_bootstrap_initializes_epoch_once():
    room = ClosedRosterState("room-1")
    state = room.bootstrap([_member("alice"), _member("bob")])

    assert state["active_epoch"]["epoch"] == 1
    assert state["policy"]["immutable_roster"] is True

    with pytest.raises(ValueError, match="already initialized"):
        room.bootstrap([_member("alice"), _member("carol")])


def test_validate_posted_envelope_normalizes_and_returns_message_payload():
    room = ClosedRosterState("room-1")
    state = room.bootstrap([_member("alice"), _member("bob")])
    normalized = room.validate_posted_envelope(_payload(state))

    assert normalized["message_type"] == OPENPGP_ENVELOPE_TYPE
    assert normalized["sender_member_id"] == "alice"
    assert normalized["armored_message"].startswith("-----BEGIN PGP MESSAGE-----")


def test_validate_posted_envelope_rejects_key_id_mismatch():
    room = ClosedRosterState("room-1")
    state = room.bootstrap([_member("alice"), _member("bob")])
    payload = _payload(state)
    payload["recipient_encryption_key_ids"] = payload["recipient_encryption_key_ids"][:1]

    with pytest.raises(ValueError, match="recipient encryption key ids do not match"):
        room.validate_posted_envelope(payload)
