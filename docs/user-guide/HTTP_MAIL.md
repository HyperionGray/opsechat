# HTTP Mail User Guide

## Overview

HTTP Mail provides disposable inboxes without SMTP or IMAP dependencies.
Messages are written and read entirely over HTTP and kept in memory only.

Core model:
- Public mailbox `address` (safe to share with senders)
- Private `read_key` (required to read/delete/destroy)
- Default-deny reads (invalid key returns access denied)
- 24-hour message expiry with in-memory overwrite on deletion

## Endpoints

All routes are scoped under `/{path}/mail`.

- `GET /{path}/mail`
  - Open the HTTP Mail UI.
- `POST /{path}/mail/new`
  - Create mailbox and return `address` + `read_key`.
- `POST /{path}/mail/{address}/send`
  - Send to a known mailbox address (JSON or form payload).
- `POST /{path}/mail/send`
  - No-JavaScript-friendly fallback: submit form data with `_address_override`.
- `GET /{path}/mail/{address}/inbox?key=<read_key>`
  - Read inbox with correct key.
- `POST /{path}/mail/{address}/delete/{message_id}`
  - Delete one message (requires `read_key`).
- `POST /{path}/mail/{address}/destroy`
  - Permanently destroy mailbox and scrub messages from memory.

## Security and lifecycle notes

- Destroyed mailboxes are removed from global storage immediately.
- Stale mailbox references are marked `destroyed` and reject future writes.
- If a send request races with mailbox destruction, the API returns HTTP `410 Gone`.
- Message and mailbox deletes overwrite in-memory contents before release.

## No-JS compose example

```bash
curl -X POST "http://127.0.0.1:5000/<path>/mail/send" \
  -d "_address_override=<mailbox-address>" \
  -d "sender=alice" \
  -d "subject=hello" \
  -d "body=message from form fallback"
```

