# OpSecChat User Guide

You have an OpSecChat URL (an `.onion` or a localhost address). This doc
walks you through everything you do in the browser from that point on.

For the operator side -- bringing the service up, finding the onion URL,
container management -- see [`QUICKSTART.md`](QUICKSTART.md).

---

## What you need

- A modern browser. **Tor Browser** for any onion URL.
- A way to talk to your peer **out of band** (in person, signal,
  whatever you already trust). You will need this to compare OpenPGP
  fingerprints.
- A few minutes of attention. The crypto is fast; the verification step
  is human.

OpSecChat does **not** install or require anything else on your machine.
Your private key never leaves the browser unless you explicitly download
the armored backup yourself.

---

## 1. Create a room

1. Open `http://<onion-or-host>/chat`.
2. Click **Create New Chat Room**.
3. The browser navigates to `/chat/room/<room-id>`.
4. Acknowledge the security-rules dialog when it appears.
5. Share the room URL with each person you want in the room. Use a
   trusted out-of-band channel; treat the URL like a meeting link.

> **Why an out-of-band channel?** The room id is an unguessable
> 256-bit token, but anyone who learns it can bring up the room shell.
> The closed-roster bootstrap (step 3 below) is the actual access
> control: only people whose public keys you add to the roster can ever
> read messages. Sharing the URL is logistics; the bootstrap is policy.

---

## 2. Generate or import your local identity

The "Local Identity" panel on the left of the room page is your
OpenPGP key pair, scoped to this room.

### Generate a new key pair (recommended for this room)

1. The **Member ID** and **Display Name** fields are pre-filled with a
   randomized suggestion. Edit if you want; otherwise keep them.
2. Optionally enter a **Private Key Passphrase**. If you do, you will
   re-enter it any time you need to decrypt a message after a browser
   reload.
3. Click **Generate Key Pair**.
4. Wait 5-15 seconds for the browser to generate the key.
5. Copy your **Public Key** (the right-hand box) and send it to your
   peer over your out-of-band channel.

### Import an existing private key

1. Fill in **Member ID** and **Display Name**.
2. Paste the armored private key into the **Private Key** box.
3. Enter the passphrase if the key is protected.
4. Click **Import Private Key**.
5. The "Public Key" field is filled in automatically.

### Back up the private key (do this now)

If you intend to use this room across browser sessions, you need the
backup. The browser warns you in the "Local Identity" panel until you
do:

1. Click **Download Private Key**.
2. The browser downloads `opsechat-<member-id>-private-key.asc`.
3. Move that file somewhere you control (encrypted disk, password
   manager, etc.). Do not leave it in `~/Downloads`.
4. The recovery banner now shows "Last private-key export: ...".

If you ever lose the browser session, re-import this same file via the
"Import Private Key" flow above.

> **Recovery vs. rotation.** Re-importing the same private key restores
> access. **Generating a new key pair** does not -- it makes you a
> different identity. To genuinely rotate keys you must create a new
> room (alpha rosters are immutable; see "Alpha caveats" below).

---

## 3. Lock the roster (epoch 1)

This is the critical step. After this, the roster is frozen.

For each person who should be in the room (other than yourself):

1. Get their **Member ID**, **Display Name**, and **Public Key** from
   them via your out-of-band channel.
2. In the **Bootstrap Epoch 1** panel:
   - Paste their Member ID into **Peer Member ID**.
   - Paste their Display Name into **Peer Display Name**.
   - Paste their armored public key into **Peer Public Key**.
3. Click **Add Member**.
4. **Verify the fingerprint.** The new member appears in the draft
   roster list with their **Signing Fingerprint** and **Encryption
   Fingerprint**. Compare both fingerprints with your peer over your
   out-of-band channel, character by character. If anything differs,
   click **Remove** and start over -- do not click Mark Verified.
5. Click **Mark Verified** once both fingerprints match.

When every peer is added and verified, click **Lock Room Roster**. The
"Active Epoch" panel now shows:

```
Epoch: 1
Roster Hash: <hex>
Members: 2
Membership changes: disabled in this alpha release
```

The "Bootstrap Epoch 1" panel disappears. The roster is now immutable.

Your peer must repeat the same fingerprint comparison from their side
and click **Mark Verified** on your roster entry. Once everyone has
verified everyone else, the composer at the bottom of the page enables
and shows:

> Ready: this message will be signed and encrypted to the full roster.

---

## 4. Send and receive messages

1. Type a message into the composer (max 500 characters by default).
2. Click **Sign + Encrypt** (or press Ctrl+Enter / Cmd+Enter).
3. The browser signs the payload with your private key, encrypts it to
   the encryption key of every roster member, and posts the armored
   block to the server.
4. Other browsers in the room poll, decrypt, validate, and render the
   plaintext message.

Each message renders with:

- The sender's display name.
- A **green "Accepted"** badge if the envelope passed every validation
  check, or a **red "Rejected"** badge with the failure reason if not.
- A note of the sender's local trust state ("Verified locally", "Pending
  local verification", "Key changed locally").

Messages auto-burn from memory after **3 minutes** (default). They never
touch disk.

---

## 5. Share the room id via one-shot DM

If you cannot send the full room URL over your out-of-band channel
(too long, or the channel is byte-limited), use the built-in DM:

1. From the chat index page (`/chat`), open the browser DevTools and
   POST to `/chat/dm/send` with `{ "room_id": "...", "message": "..." }`,
   **or** integrate it into your own tooling.
2. The response gives you a `dm_url` that resolves to a single-use
   message containing the room id. The DM expires in **60 seconds**.

(A first-class DM UI lives behind a beta flag; the JSON endpoint above
is the alpha surface.)

---

## 6. What the trust badges mean

| Badge / note               | Meaning                                                                                                  |
|----------------------------|----------------------------------------------------------------------------------------------------------|
| **New**                    | This browser has never seen this Member ID before.                                                       |
| **Pending Verification**   | This browser has the keys but they have not been confirmed against the out-of-band fingerprint check.    |
| **Verified**               | You clicked Mark Verified after comparing fingerprints out of band.                                      |
| **Changed Key**            | The Member ID is the same as one you previously verified, but at least one fingerprint differs. **Stop.** Treat this as a key compromise or a hostile rebootstrap. Create a new room. |
| **Accepted** (on a message)| The envelope passed every server-side and browser-side validation check.                                 |
| **Rejected** (on a message)| The envelope failed at least one validation check; the failure reason is shown in the message body.      |

---

## 7. Recovering from a browser reload

If you close the tab without setting a passphrase, the in-memory key is
lost. You will need the backup file.

1. Re-open the same `/chat/room/<room-id>` URL.
2. Acknowledge the security warning.
3. Fill in your same **Member ID** and **Display Name**.
4. Paste the armored backup into **Private Key**.
5. Enter the passphrase if you set one.
6. Click **Import Private Key**.

The local trust store (which peers you previously verified) is also
session-scoped. After re-import, you will need to re-verify your peers
from the active-roster list. Compare fingerprints out of band again --
the keys themselves should still match what you locked into epoch 1.

---

## 8. Alpha caveats

These are intentional limits in this release. They are tracked for
beta. See [`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md) for the full list.

1. **Rosters are immutable.** Once you lock epoch 1, you cannot add,
   remove, or rotate a member's keys in this room. To change membership
   or rotate a key, **create a new room** and bootstrap a new roster.
2. **The browser is the crypto owner.** The local OpenPGP private key
   lives in the browser session. Always keep an armored backup outside
   the browser; the in-room flow above guides you through this.
3. **Messages auto-burn after 3 minutes.** The server overwrites their
   text in memory before deletion. There is no message history. There
   is no "scroll back".
4. **Rooms expire after 1 hour of inactivity.** If you walk away for
   long enough, you will need to create a new room.
5. **Recipient anonymity is sender-vs-server only.** Roster members can
   always see each other; that is what "closed roster" means.

---

## 9. Troubleshooting

| Symptom                                         | Fix                                                                                                                |
|-------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| "Room not found or expired"                     | The room id is wrong, the room timed out (1h idle), or the operator restarted the service. Create a new room.      |
| Composer stays disabled after roster lock       | Check the "Active Epoch" panel: every non-local member must show **Verified** locally. Click **Mark Verified**.    |
| "Rate limit exceeded"                           | You are hitting the per-session rate limit. Wait a minute. If this is a real DOS concern, the operator can tune `RATE_LIMITS` in `simple_chat_routes.py`. |
| "Sender is not part of the room roster"         | The sender's local identity does not match any roster entry. They probably regenerated keys; the roster is locked. |
| "Roster hash mismatch"                          | One side is on a different epoch. Refresh both browsers; if it persists, create a new room.                        |
| "Recipient set does not match the room roster"  | The sender's browser is out of sync with the roster. Refresh and try again.                                        |
| "Anonymous recipients are forbidden"            | The sender attempted to use OpenPGP wildcard recipients. The room rejects this by design. Create a new room.       |

If a problem is none of the above, capture the message body, the
"Active Epoch" panel, and the browser console output, and file an issue.
