# HTTP Mail User Guide

HTTP Mail is an email-like system that runs entirely over HTTP and keeps data in memory only.
It does not require SMTP, IMAP, or POP.

## Overview

Each mailbox has:
- a public mailbox address (share with senders)
- a private read key (keep secret)

Anyone with the address can send a message.
Only someone with the read key can read or delete messages.

## Routes

Assume your app path is `{path}`.

- `GET /{path}/mail`
  - Open the HTTP Mail UI.
- `POST /{path}/mail/new`
  - Create a mailbox and return `{address, read_key}`.
- `POST /{path}/mail/send`
  - No-JavaScript fallback send endpoint.
  - Requires form field `_address_override` (or JSON field `address`).
- `POST /{path}/mail/{address}/send`
  - Send directly to a known mailbox address.
- `GET /{path}/mail/{address}/inbox?key={read_key}`
  - Read inbox (403 on invalid key).
- `POST /{path}/mail/{address}/delete/{message_id}`
  - Delete one message (requires `read_key`).
- `POST /{path}/mail/{address}/destroy`
  - Destroy mailbox and scrub all messages (requires `read_key`).

## Security properties

- Default deny inbox access with timing-safe key comparison.
- Message delete/destroy scrubs message content before removal.
- Messages expire after 24 hours.
- Input fields are sanitized before storage.
- Messages that sanitize to empty body are rejected.

## Example (JSON API)

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/{path}/mail/new"
```

Send message:

```bash
curl -s -X POST "http://localhost:5000/{path}/mail/{address}/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'
```

Read inbox:

```bash
curl -s "http://localhost:5000/{path}/mail/{address}/inbox?key={read_key}" \
  -H "Accept: application/json"
```

