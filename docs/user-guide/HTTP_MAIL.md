# HTTP Mail Guide

## Overview

HTTP Mail provides a mailbox-style messaging workflow without SMTP or IMAP.
It is fully in-memory and protected by a private read key.

Core model:

- Mailbox address: share with senders
- Read key: keep secret, required to read inbox and manage mailbox
- Message retention: 24 hours in memory, then overwritten and removed

## Routes

All routes are namespaced under `/{path}/mail`.

- `GET /{path}/mail` - HTTP Mail UI
- `POST /{path}/mail/new` - create mailbox
- `POST /{path}/mail/send` - send by address in payload/form (`address` or `_address_override`)
- `POST /{path}/mail/{address}/send` - send directly to mailbox address
- `GET /{path}/mail/{address}/inbox?key={read_key}` - read inbox
- `POST /{path}/mail/{address}/delete/{msg_id}` - delete one message
- `POST /{path}/mail/{address}/rotate-key` - rotate read key
- `POST /{path}/mail/{address}/destroy` - destroy mailbox and wipe messages

## Security Properties

- Default deny: inbox read returns 403 with invalid/missing key
- Read-key authentication uses constant-time comparison
- Mailbox destroy performs overwrite before data release
- Destroyed mailboxes reject additional writes
- Message and mailbox contents are never persisted by this subsystem

## New Feature: Read-Key Rotation

Read-key rotation lets mailbox owners invalidate a leaked/old key immediately.

Behavior:

1. Call rotate endpoint with current key
2. Server issues a new 32-char key
3. Old key instantly stops working
4. Inbox access and destructive actions require the new key

Example:

```bash
curl -X POST "http://localhost:5001/SECRET_PATH/mail/ADDRESS/rotate-key" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"read_key":"CURRENT_KEY"}'
```

Success response:

```json
{
  "success": true,
  "read_key": "NEW_KEY",
  "inbox_url": "/SECRET_PATH/mail/ADDRESS/inbox?key=NEW_KEY"
}
```

## Testing

Run HTTP Mail tests:

```bash
PYTHONPATH=. pytest tests/test_http_mail.py -q
```

The test suite covers:

- mailbox lifecycle create/read/send/delete/destroy
- key rotation success/failure
- default-deny reads
- route behavior for JSON and non-JS form paths
