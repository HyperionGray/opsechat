# HTTP Mail API

SMTP-free mailboxes for short-lived message exchange over plain HTTP.

## Overview

The HTTP mail subsystem provides disposable in-memory mailboxes without SMTP/IMAP setup:

- Create a mailbox and receive:
  - `address` (public, shareable)
  - `read_key` (private, required for read/status/delete/destroy)
- Anyone can send to a mailbox address.
- Only holders of the `read_key` can read inbox contents or mailbox stats.
- Messages expire automatically after 24 hours.
- Destroyed mailboxes reject further writes, including stale in-memory references.

## Endpoints

All routes are mounted under `/<path>/mail`.

### Create mailbox

`POST /<path>/mail/new`

Response:

```json
{
  "success": true,
  "address": "publicMailboxId",
  "read_key": "privateReadKey",
  "send_url": "/<path>/mail/publicMailboxId/send",
  "inbox_url": "/<path>/mail/publicMailboxId/inbox"
}
```

### Send message

`POST /<path>/mail/<address>/send`

Accepts JSON or form data:

- `subject` (optional)
- `body` (required)
- `sender` (optional; defaults to `anonymous`)

If mailbox was destroyed between lookup and write, returns HTTP `410`.

### Read inbox

`GET /<path>/mail/<address>/inbox?key=<read_key>`

Returns mailbox messages (JSON when `Accept: application/json`).

### Mailbox status (new)

`GET /<path>/mail/<address>/status?key=<read_key>`

Returns JSON metadata:

```json
{
  "address": "publicMailboxId",
  "message_count": 2,
  "created_at": "2026-03-21T15:00:00.000000",
  "message_ttl_hours": 24,
  "inbox_url": "/<path>/mail/publicMailboxId/inbox"
}
```

### Delete one message

`POST /<path>/mail/<address>/delete/<msg_id>`

Requires `read_key` in JSON body or form data.

### Destroy mailbox

`POST /<path>/mail/<address>/destroy`

Requires `read_key` in JSON body or form data. Mailbox data is overwritten in memory before removal.

## Security Notes

- `read_key` checks use constant-time comparison.
- Message and sender fields are sanitized on write.
- Mailbox destruction is lock-protected to avoid stale-reference write races.
- No SMTP credentials are required for this subsystem.
