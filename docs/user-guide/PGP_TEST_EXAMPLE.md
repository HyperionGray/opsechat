# Closed-Roster OpenPGP Test Example

This example shows the current simple-room alpha flow for two members, Alice and Bob.

## Setup

### Alice

1. Creates a room
2. Generates or imports her OpenPGP identity
3. Adds Bob's public key
4. Verifies Bob's fingerprints out of band
5. Locks epoch 1

### Bob

1. Opens the room URL
2. Imports the OpenPGP identity that matches his roster entry
3. Verifies Alice's fingerprints out of band

## Message Flow

### Alice sends a message

Alice types:

```text
Hello Bob, this is secret.
```

The browser creates a signed payload like:

```json
{
  "type": "closed_roster_openpgp_v1",
  "room_id": "<room_id>",
  "epoch": 1,
  "sender_member_id": "alice",
  "sender_signing_fingerprint": "<alice_signing_fp>",
  "roster_hash": "<roster_hash>",
  "recipient_encryption_fingerprints": [
    "<alice_encryption_fp>",
    "<bob_encryption_fp>"
  ],
  "intended_recipient_fingerprints": [
    "<alice_encryption_fp>",
    "<bob_encryption_fp>"
  ],
  "sent_at": "2026-04-26T00:00:00Z",
  "text": "Hello Bob, this is secret."
}
```

That payload is then encrypted and signed into an armored OpenPGP message before upload.

## Receive-Side Checks

When Bob polls the room, the browser:

1. decrypts the OpenPGP envelope
2. verifies Alice's signature
3. checks `room_id`
4. checks `epoch`
5. checks `roster_hash`
6. checks the recipient set against the active roster
7. rejects the message if any check fails

## Expected Result

Bob sees:

```text
Alice: Hello Bob, this is secret.
```

with a local note that Alice is either:

- verified locally
- pending local verification
- or rejected if the key changed or validation failed

## Alpha Caveat

If Bob's or Alice's key changes, the current alpha workflow is:

1. stop using the room
2. create a new room
3. bootstrap a new epoch-1 roster
