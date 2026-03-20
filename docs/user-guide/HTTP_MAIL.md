# HTTP Mail

HTTP Mail provides mailbox-style messaging over HTTP with no SMTP or IMAP dependency.

## Overview

- Create a mailbox to receive:
  - `address` (public, share with senders)
  - `read_key` (private, required to read/delete messages)
- Anyone with the mailbox address can send messages.
- Only holders of the read key can read the inbox.
- Messages expire after 24 hours and are stored in memory only.

## Routes

All routes are scoped under `/<path>/mail`.

- `GET /<path>/mail` - HTTP Mail web UI
- `POST /<path>/mail/new` - Create mailbox
- `POST /<path>/mail/<address>/send` - Send message
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - Read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>` - Delete one message
- `POST /<path>/mail/<address>/rotate-key` - Rotate read key
- `POST /<path>/mail/<address>/destroy` - Destroy mailbox

## New: Read Key Rotation

Read key rotation lets a mailbox owner invalidate a previously shared or exposed key
without deleting the mailbox.

Behavior:

1. Call rotate-key with the current key.
2. Service returns a new key.
3. Old key is immediately denied.
4. Existing messages remain accessible with the new key.

Example:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/rotate-key" \
  -H "Content-Type: application/json" \
  -d '{"read_key":"CURRENT_KEY"}'
```

Response:

```json
{
  "success": true,
  "new_read_key": "NEW_KEY"
}
```

## Security Notes

- Treat `read_key` like a password.
- Regenerate keys after accidental sharing.
- Message body is sanitized and length-limited.
- Mailboxes and messages are in-memory only.
