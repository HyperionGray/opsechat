# Closed-Roster OpenPGP Usage

OpSecChat simple rooms now use an explicit closed-roster OpenPGP flow instead of the old shared room-key model.

## What Changed

- Every room has an explicit active roster and roster hash.
- Each message is signed by the sender and encrypted to the full roster.
- Verification is local to each browser session.
- The alpha release keeps room rosters immutable after bootstrap.

## Room Workflow

### 1. Create the room

1. Open `/chat`
2. Create a room
3. Share the URL only with the people who should be in the roster

### 2. Set your local identity

Inside the room:

1. Enter your `member_id`
2. Enter a display name
3. Generate a new key pair or import an existing private key
4. Download the armored private-key backup and store it outside the browser session
5. Keep the public key available for the rest of the roster

Notes:

- The private key stays in browser session storage for this tab/session.
- The room UI now records whether you exported a private-key backup in the current browser session.
- If the key is passphrase protected, re-enter the passphrase after a reload.
- If you clear the local identity or lose the session, re-import the same armored private key to recover access.

### 3. Bootstrap epoch 1

Before the first room message:

1. Add every planned member's public key
2. Verify fingerprints out of band
3. Mark each member verified locally
4. Lock the room roster

Locking the roster creates:

- `epoch = 1`
- a canonical member list
- a deterministic `roster_hash`

## Sending Messages

Once the room has an active epoch and every non-local member is locally verified:

1. Type the message
2. Click `Sign + Encrypt`
3. The browser signs the payload with your private key
4. The browser encrypts the payload to every roster member's public key
5. The server stores only the armored OpenPGP envelope plus roster metadata

## Receiving Messages

For every room message, the browser:

1. Decrypts the OpenPGP message with the local private key
2. Verifies the message signature
3. Checks the active room id, epoch, and roster hash
4. Checks the sender against the active roster
5. Checks the recipient set against the active roster
6. Rejects the message if any check fails

## Trust States

Each observed member can appear in one of these states:

- `new`: first time this `member_id` and key pair were observed
- `known`: same `member_id` and same fingerprints as before
- `changed`: same `member_id`, different fingerprints
- `verified`: you completed the out-of-band fingerprint check locally

`verified` is local only. One participant verifying a key does not verify it for anyone else.

## Alpha Release Limits

- Membership changes are not supported inside an active room yet.
- If a member key changes, stop using that room and create a new one.
- The browser is still the local crypto owner for simple rooms in this alpha.
- Intended-recipient packet subpacket parsing is not enforced yet.
- Key revocation and in-room key rotation flows are not implemented yet.

## Key Generation Outside the Browser

You can bring an existing OpenPGP key:

```bash
gpg --gen-key
gpg --armor --export your-id@example.invalid > public-key.asc
gpg --armor --export-secret-keys your-id@example.invalid > private-key.asc
```

Import the private key into the room UI and share only the public key with the roster.

## Technical Notes

- Uses the bundled OpenPGP.js client library
- Uses armored OpenPGP messages for transport simplicity
- Uses explicit packet key ids by disabling wildcard recipients
- Stores room state and messages in memory only on the server
