# HTTP Mail Read-Key Rotation

## Summary

HTTP Mail now supports secure read-key rotation. This allows mailbox owners to invalidate a leaked or shared key without recreating the mailbox.

## Motivation

Recent HTTP Mail work added robust mailbox destruction semantics and explicit in-memory scrubbing. A related operational gap remained: if a read key is exposed, the mailbox owner previously had to destroy the mailbox and start over.

Read-key rotation addresses that gap while preserving:

- default-deny inbox access
- no-disk in-memory behavior
- sender-facing mailbox address stability

## What Was Implemented

### Backend (`http_mail_system.py`)

- `HttpMailbox.destroyed` state is now explicit and initialized on creation.
- `HttpMailbox.add_message(...)` now refuses writes after destruction.
- `HttpMailbox.destroy()` performs one-way teardown:
  - marks mailbox as destroyed
  - overwrites existing messages
  - clears message list
- `HttpMailbox.rotate_read_key(current_read_key)`:
  - validates current key
  - generates a fresh 24-byte URL-safe token (32 chars)
  - atomically replaces the key
- `HttpMailStorage.rotate_mailbox_read_key(address, read_key)` added as a storage-level API.
- `HttpMailStorage.delete_mailbox(...)` now delegates scrubbing and teardown to `mailbox.destroy()`.

### Routes (`http_mail_routes.py`)

New endpoint:

- `POST /<path>/mail/<address>/rotate-key`

Behavior:

- Requires current `read_key`
- Returns `403` on invalid key or unknown mailbox
- Returns JSON on API usage:
  - `{ "success": true, "new_read_key": "..." }`
- Returns rendered HTML for form usage, including the rotated key.

Additional hardening:

- Send route now returns `410` if a stale mailbox reference is destroyed before write.

### UI (`templates/http_mail.html`)

- Added "Rotate Read Key" control in both:
  - server-rendered inbox section
  - JavaScript-rendered inbox section
- After JS rotation:
  - `read-key` input updates to the new key
  - inbox refreshes with the new key
- Added explicit warning panel when a key is rotated server-side.

## API Example

```bash
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"read_key":"CURRENT_KEY"}' \
  "http://localhost:5000/<path>/mail/<address>/rotate-key"
```

Success response:

```json
{
  "success": true,
  "new_read_key": "NEW_32_CHAR_KEY"
}
```

## Security Notes

- Rotation invalidates the old key immediately.
- Mailbox address does not change, so sender-side links remain valid.
- No key history is retained.
- Destroyed mailbox objects reject future writes, even if a stale reference exists.
