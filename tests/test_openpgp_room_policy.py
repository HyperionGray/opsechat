"""
Tests for closed-roster OpenPGP room policy helpers.
"""

import hashlib
import pytest

from openpgp_room_policy import (
    MessageEnvelopeMetadata,
    PendingRosterChange,
    RoomEpoch,
    RoomMember,
    TrustStore,
    hash_roster,
    normalize_fingerprint,
    validate_message_for_epoch,
)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()


def _member(member_id: str, display_name: str | None = None) -> RoomMember:
    base = member_id.upper()
    return RoomMember(
        member_id=member_id,
        signing_fingerprint=_fp(f"{base}A"),
        encryption_fingerprint=_fp(f"{base}B"),
        display_name=display_name or member_id,
    )


def test_normalize_fingerprint_strips_separators():
    raw = "AA BB:CC-DD EE:FF 00-11 22 33:44 55 66-77 88 99:AA BB CC DD EE FF 00 11 22 33 44 55 66 77 88 99"
    normalized = normalize_fingerprint(raw)

    assert normalized == "AABBCCDDEEFF00112233445566778899AABBCCDDEEFF00112233445566778899"


def test_trust_store_detects_key_change_without_replacing_existing_identity():
    trust = TrustStore()
    bob = _member("bob")

    assert trust.observe(bob) == "new"
    trust.mark_verified("bob")

    changed_bob = RoomMember(
        member_id="bob",
        signing_fingerprint=_fp("C"),
        encryption_fingerprint=_fp("D"),
        display_name="Bob",
    )

    assert trust.observe(changed_bob) == "changed"
    assert trust.expected_identity("bob").signing_fingerprint == bob.signing_fingerprint
    assert trust.is_verified("bob") is True


def test_verification_is_local_to_each_trust_store():
    alice_store = TrustStore()
    carol_store = TrustStore()
    bob = _member("bob")

    alice_store.observe(bob)
    carol_store.observe(bob)
    alice_store.mark_verified("bob")

    assert alice_store.is_verified("bob") is True
    assert carol_store.is_verified("bob") is False


def test_roster_hash_is_stable_regardless_of_member_order():
    alice = _member("alice")
    bob = _member("bob")
    carol = _member("carol")

    hash_one = hash_roster([alice, bob, carol])
    hash_two = hash_roster([carol, alice, bob])

    assert hash_one == hash_two


def test_room_epoch_rejects_duplicate_signing_fingerprints():
    alice = _member("alice")
    alias = RoomMember(
        member_id="alias",
        signing_fingerprint=alice.signing_fingerprint,
        encryption_fingerprint=_fp("Z"),
        display_name="Alias",
    )

    with pytest.raises(ValueError, match="signing fingerprints"):
        RoomEpoch(room_id="room-1", epoch=1, members=(alice, alias))


def test_pending_change_requires_locally_verified_added_members_before_approval():
    alice = _member("alice")
    bob = _member("bob")
    carol = _member("carol")
    current = RoomEpoch(room_id="room-1", epoch=1, members=(alice, bob))
    pending = PendingRosterChange(current_epoch=current, proposed_members=(alice, bob, carol))

    trust = TrustStore()
    trust.observe(carol)

    with pytest.raises(ValueError, match="not locally verified"):
        pending.approve(alice.signing_fingerprint, trust)


def test_pending_change_requires_unanimous_approvals_and_candidate_ack():
    alice = _member("alice")
    bob = _member("bob")
    carol = _member("carol")
    current = RoomEpoch(room_id="room-1", epoch=1, members=(alice, bob))
    pending = PendingRosterChange(current_epoch=current, proposed_members=(alice, bob, carol))

    alice_store = TrustStore()
    bob_store = TrustStore()
    alice_store.observe(carol)
    bob_store.observe(carol)
    alice_store.mark_verified("carol")
    bob_store.mark_verified("carol")

    pending.approve(alice.signing_fingerprint, alice_store)
    assert pending.ready_to_activate() is False

    pending.approve(bob.signing_fingerprint, bob_store)
    assert pending.ready_to_activate() is False

    pending.acknowledge_candidate(carol.signing_fingerprint)
    assert pending.ready_to_activate() is True

    next_epoch = pending.activate()
    assert next_epoch.epoch == 2
    assert next_epoch.member_ids() == {"alice", "bob", "carol"}


def test_validate_message_rejects_anonymous_or_mismatched_recipient_sets():
    alice = _member("alice")
    bob = _member("bob")
    epoch = RoomEpoch(room_id="room-1", epoch=3, members=(alice, bob))

    envelope = MessageEnvelopeMetadata(
        room_id="room-1",
        epoch=3,
        sender_signing_fingerprint=alice.signing_fingerprint,
        roster_hash=epoch.roster_hash,
        recipient_encryption_fingerprints=frozenset({bob.encryption_fingerprint}),
        intended_recipient_fingerprints=frozenset({bob.encryption_fingerprint}),
        anonymous_recipients=True,
        decryption_ok=True,
        integrity_ok=True,
        signature_ok=True,
    )

    result = validate_message_for_epoch(epoch, envelope, bob.encryption_fingerprint)

    assert result.accepted is False
    assert "anonymous recipients are forbidden" in result.errors
    assert "recipient set does not match the room roster" in result.errors
    assert "intended recipient fingerprints do not match the room roster" in result.errors


def test_validate_message_accepts_exact_room_roster():
    alice = _member("alice")
    bob = _member("bob")
    epoch = RoomEpoch(room_id="room-1", epoch=3, members=(alice, bob))

    envelope = MessageEnvelopeMetadata(
        room_id="room-1",
        epoch=3,
        sender_signing_fingerprint=alice.signing_fingerprint,
        roster_hash=epoch.roster_hash,
        recipient_encryption_fingerprints=epoch.encryption_fingerprints(),
        intended_recipient_fingerprints=epoch.encryption_fingerprints(),
        anonymous_recipients=False,
        decryption_ok=True,
        integrity_ok=True,
        signature_ok=True,
    )

    result = validate_message_for_epoch(epoch, envelope, bob.encryption_fingerprint)

    assert result.accepted is True
    assert result.errors == ()
