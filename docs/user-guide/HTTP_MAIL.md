# HTTP Mail User Guide

## Overview

HTTP Mail is an in-memory mailbox system that does not require SMTP or IMAP.
Each mailbox has:

- A public `address` (safe to share with senders)
- A private `read_key` (required to read, delete, rotate key, or destroy mailbox)

Default-deny behavior is enforced: without the correct key, inbox access is denied.

## Security model

- Messages are stored in memory only (no disk persistence)
- Messages expire after 24 hours
- Message content is overwritten in memory before deletion
- Mailboxes can be destroyed immediately
- Read keys can be rotated if a key is exposed

## Quick start

1. Open `/{path}/mail`
2. Create a mailbox
3. Save the generated read key immediately
4. Share the mailbox address with senders
5. Read inbox at:
   - Browser UI: use the "Read My Inbox" section
   - JSON API: `GET /{path}/mail/<address>/inbox?key=<read_key>`

## API endpoints

All endpoints are scoped under `/{path}/mail`.

- `POST /new`
  - Create mailbox
  - Returns `address`, `read_key`, `send_url`, `inbox_url`

- `POST /<address>/send`
  - Send message to mailbox (no auth required)
  - Accepts JSON or form fields: `subject`, `body`, `sender`

- `GET /<address>/inbox?key=<read_key>`
  - Read mailbox (requires read key)

- `POST /<address>/delete/<msg_id>`
  - Delete one message (requires read key)

- `POST /<address>/rotate-key`
  - Rotate mailbox read key (requires current read key)
  - JSON response includes `new_read_key`
  - Old read key is immediately invalidated

- `POST /<address>/destroy`
  - Destroy mailbox and all messages (requires read key)

## Read-key rotation workflow

Use key rotation when you suspect the read key was exposed:

1. Call `POST /{path}/mail/<address>/rotate-key` with current `read_key`
2. Save the returned `new_read_key`
3. Replace old key anywhere it was stored
4. Verify old key no longer works

## JSON examples

Create mailbox:

```json
POST /abc123/mail/new
{
  "success": true,
  "address": "Q4qgYB8eqnqf",
  "read_key": "M5IJvj1J0L6H_hW2x6Qxx_UTR9fH8fGQ",
  "send_url": "/abc123/mail/Q4qgYB8eqnqf/send",
  "inbox_url": "/abc123/mail/Q4qgYB8eqnqf/inbox"
}
```

Rotate key:

```json
POST /abc123/mail/Q4qgYB8eqnqf/rotate-key
{"read_key": "current_key"}

{
  "success": true,
  "new_read_key": "new_key_value"
}
```
