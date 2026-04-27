# Closed-Roster OpenPGP Plan

## Goal

Replace the current browser-room key-sharing model with a small-group trust model that is explicit, auditable, and hostile to silent membership expansion.

The target use case is a planned group where:

- every member knows every other member's keys out of band
- every member decides locally whether another member is verified
- no single inviter can silently add a new reader
- all room messages are signed by the sender and encrypted to the full roster

## Non-Goals

- No attempt to make the current browser room toggle count as real end-to-end encryption
- No transitive trust such as "Alice verified Bob, therefore Carol should trust Bob"
- No hidden recipients, wildcard recipients, or silent reader additions
- No automatic forward secrecy in v1

## Application Model

### 1. Local trust store

Each device keeps a local trust store with these states:

- `new`: first time this application identifier and key pair were observed
- `known`: same identifier and same fingerprints as before
- `changed`: same identifier but different signing or encryption fingerprint
- `verified`: local operator completed out-of-band verification

Verification is local and pairwise. Alice verifying Bob does not verify Bob for Carol.

### 2. Room member record

Each roster entry binds:

- `member_id`: operator-facing application identifier
- `signing_fingerprint`
- `encryption_fingerprint`
- `display_name`

Authentication is based on fingerprints, not on the display name.

### 3. Room epoch

Each room has an explicit epoch:

- `room_id`
- `epoch`
- canonical roster
- `roster_hash`

The roster hash is a deterministic SHA-256 over the canonical roster encoding and acts as a compact room-membership commitment.

## Membership Rules

### Add member

To add a member:

1. Each existing member obtains and verifies the candidate's fingerprints out of band.
2. Each existing member records a local approval.
3. The candidate acknowledges the full proposed roster.
4. The room advances to a new epoch only after unanimous approval from the current roster and acknowledgement from all added members.

### Remove member

To remove a member:

1. Current members approve the removal.
2. A new epoch is created with the reduced roster.
3. Future messages are encrypted only to the new roster.

Removal does not require acknowledgement from the removed member.

### Key change

If a known `member_id` presents new fingerprints:

- raise a local security alert
- do not silently replace the old trust record
- require a new out-of-band verification and a new room epoch

## Message Envelope Policy

Every accepted room message must carry signed metadata with:

- `room_id`
- `epoch`
- sender signing fingerprint
- roster hash
- recipient encryption fingerprint set
- intended recipient fingerprint set when supported

Receive-side policy is fail-closed:

- decryption must succeed
- integrity check must succeed
- signature verification must succeed
- sender must be in the roster
- recipient set must exactly match the room roster
- anonymous recipients are forbidden
- roster hash must match the active epoch

## Recommended OpenPGP Rules

- Use ASCII armor for transport simplicity.
- Prefer version 6 keys when all participants support them.
- Prefer AEAD-capable encrypted containers when all participants support them.
- Require sender signatures on all room messages.
- Reject anonymous or wildcard recipient modes.
- Generate and verify intended-recipient fingerprints when available.

## Repo Migration Plan

### Phase 1: policy layer

- add pure-policy state for trust stores, room epochs, roster hashes, and pending membership changes
- add receive-side validation rules
- document operator workflow

### Phase 2: local crypto owner

- move key import, decryption, signing, and encryption into a local process or TUI-first path
- keep browser UI as a shell, not the source of trust

### Phase 3: room message rewrite

- replace server-issued shared room keys
- produce signed+encrypted OpenPGP envelopes per room message
- validate roster metadata on receive

### Phase 4: operational UX

- explicit "pending verification" state
- explicit "changed key" alarms
- explicit room-epoch transition flow for membership changes

## Current Implementation Status

The repo now partially implements this protocol for simple web rooms.

Implemented in the current alpha path:

- local trust decisions in `openpgp_room_policy.py`
- immutable epoch-1 roster bootstrap for `/chat/room/<room_id>`
- signed and encrypted OpenPGP room envelopes in the browser client
- fail-closed receive-side validation in the browser client
- explicit pending-verification and changed-key room UX
- retirement of the old shared room-key endpoint

Still not implemented:

- signed room-epoch transition workflow for add/remove/key-rotation
- packet-level intended-recipient subpacket verification
- a non-browser local crypto owner such as a TUI-first or local-process path
