# HTTP Mail Guide

## Overview

HTTP Mail is a lightweight mailbox system that works over HTTP only (no SMTP/IMAP).
Each mailbox has:

- **Address**: share with senders
- **Read key**: keep private; required to read/delete/rotate key/destroy mailbox

Messages are in-memory and expire automatically after 24 hours.

## Routes

All routes are under `/{path}/mail`.

- `POST /new` - create mailbox
- `POST /<address>/send` - send message (no auth required)
- `GET /<address>/inbox?key=<read_key>` - read inbox
- `POST /<address>/delete/<message_id>` - delete one message
- `POST /<address>/rotate-key` - rotate read key
- `POST /<address>/destroy` - destroy mailbox

## New: Read Key Rotation

Use read-key rotation to invalidate a leaked or overused key without deleting the mailbox.

### JSON Example

```bash
curl -X POST "http://localhost/{path}/mail/<address>/rotate-key" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"read_key":"<current_read_key>"}'
```

Successful response:

```json
{
  "success": true,
  "address": "<address>",
  "new_read_key": "<new_key>"
}
```

After rotation:

- old key immediately stops working
- new key is required for inbox access and message deletion

## Safety Notes

- Destroyed mailboxes reject further writes.
- Message content is overwritten in memory before delete/destroy operations.
- Keep read keys out of logs, screenshots, and shared terminals.
