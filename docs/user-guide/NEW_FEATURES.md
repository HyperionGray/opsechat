# New Features Guide - v0.8.0 Alpha

This guide covers the current alpha-facing features for simple rooms after the closed-roster OpenPGP rewrite.

## Closed-Roster OpenPGP Rooms

### What Changed

The old shared room-key flow has been removed from simple rooms.

Simple rooms now use:

- explicit epoch-1 roster bootstrap
- per-member public keys
- signed room messages
- encryption to the full roster
- local trust states for `new`, `known`, `changed`, and `verified`

### Operator Flow

1. Create a room at `/chat`
2. Generate or import the local OpenPGP identity
3. Add every member's public key
4. Verify fingerprints out of band
5. Lock the room roster
6. Send signed and encrypted messages to the full roster

### Alpha Constraint

Active room rosters are immutable in this release.

If a member must be added, removed, or rotated:

1. create a new room
2. bootstrap a new roster
3. continue there

## Room State API

### Create a room

```bash
curl -X POST http://localhost:5001/chat/create
```

### Fetch room state

```bash
curl http://localhost:5001/chat/room/<room_id>/state
```

### Bootstrap epoch 1

```bash
curl -X POST http://localhost:5001/chat/room/<room_id>/state/bootstrap \
  -H 'Content-Type: application/json' \
  -d '{
    "creator_member_id": "alice",
    "members": [
      {
        "member_id": "alice",
        "display_name": "Alice",
        "signing_fingerprint": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "encryption_fingerprint": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "signing_key_id": "AAAAAAAAAAAAAAAA",
        "encryption_key_id": "BBBBBBBBBBBBBBBB",
        "public_key_armored": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n...\n-----END PGP PUBLIC KEY BLOCK-----"
      }
    ]
  }'
```

### Post a room message envelope

```bash
curl -X POST http://localhost:5001/chat/room/<room_id>/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "envelope_type": "closed_roster_openpgp_v1",
    "room_id": "<room_id>",
    "epoch": 1,
    "sender_member_id": "alice",
    "sender_signing_fingerprint": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "roster_hash": "<roster_hash>",
    "recipient_encryption_fingerprints": ["BBBB..."],
    "intended_recipient_fingerprints": ["BBBB..."],
    "recipient_encryption_key_ids": ["BBBBBBBBBBBBBBBB"],
    "armored_message": "-----BEGIN PGP MESSAGE-----\n...\n-----END PGP MESSAGE-----"
  }'
```

## Direct Messages

Ephemeral DMs are still available for sharing room URLs out of band:

- 60-second expiry
- in-memory only
- simple text only

## Retired Endpoint

The old shared-room-key endpoint is intentionally deprecated:

```bash
GET /chat/room/<room_id>/key
```

It now returns `410 Gone`.
