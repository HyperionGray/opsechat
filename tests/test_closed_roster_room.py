import hashlib

import pytest

from closed_roster_room import ClosedRosterState, OPENPGP_ENVELOPE_TYPE


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()


def _key_id(seed: str) -> str:
    return _fp(seed)[:16]


def _member(member_id: str) -> dict:
    return {
        "member_id": member_id,
        "display_name": member_id.title(),
        "signing_fingerprint": _fp(f"{member_id}-sign"),
        "encryption_fingerprint": _fp(f"{member_id}-enc"),
        "signing_key_id": _key_id(f"{member_id}-sign-key"),
        "encryption_key_id": _key_id(f"{member_id}-enc-key"),
        "public_key_armored": (
            "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
            f"{member_id}\n"
            "-----END PGP PUBLIC KEY BLOCK-----"
        ),
    }


def _valid_payload(state: dict) -> dict:
    epoch = state["active_epoch"]
    alice = next(member for member in epoch["members"] if member["member_id"] == "alice")
    return {
        "envelope_type": OPENPGP_ENVELOPE_TYPE,
        "room_id": epoch["room_id"],
        "epoch": epoch["epoch"],
        "sender_member_id": "alice",
        "sender_signing_fingerprint": alice["signing_fingerprint"],
        "roster_hash": epoch["roster_hash"],
        "recipient_encryption_fingerprints": [
            member["encryption_fingerprint"] for member in epoch["members"]
        ],
        "intended_recipient_fingerprints": [
            member["encryption_fingerprint"] for member in epoch["members"]
        ],
        "recipient_encryption_key_ids": [member["encryption_key_id"] for member in epoch["members"]],
        "armored_message": "-----BEGIN PGP MESSAGE-----\nopaque\n-----END PGP MESSAGE-----",
    }


def test_serialize_default_state():
    state = ClosedRosterState("room-1").serialize()
    assert state["mode"] == OPENPGP_ENVELOPE_TYPE
    assert state["active_epoch"] is None
    assert state["policy"]["immutable_roster"] is True
    assert state["policy"]["shared_room_keys_supported"] is False


def test_bootstrap_sets_immutable_epoch():
    room = ClosedRosterState("room-1")
    state = room.bootstrap([_member("alice"), _member("bob")])
    assert state["active_epoch"]["epoch"] == 1
    assert state["active_epoch"]["immutable_roster"] is True
    assert len(state["active_epoch"]["members"]) == 2


def test_bootstrap_twice_rejected():
    room = ClosedRosterState("room-1")
    room.bootstrap([_member("alice"), _member("bob")])
    with pytest.raises(ValueError, match="already initialized"):
        room.bootstrap([_member("alice")])


def test_validate_posted_envelope_success():
    room = ClosedRosterState("room-1")
    state = room.bootstrap([_member("alice"), _member("bob")])
    normalized = room.validate_posted_envelope(_valid_payload(state))
    assert normalized["message_type"] == OPENPGP_ENVELOPE_TYPE
    assert normalized["sender_member_id"] == "alice"


def test_validate_posted_envelope_rejects_key_id_mismatch():
    room = ClosedRosterState("room-1")
    state = room.bootstrap([_member("alice"), _member("bob")])
    payload = _valid_payload(state)
    payload["recipient_encryption_key_ids"] = payload["recipient_encryption_key_ids"][:1]
    with pytest.raises(ValueError, match="recipient encryption key ids do not match"):
        room.validate_posted_envelope(payload)
