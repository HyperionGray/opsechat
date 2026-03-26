# HTTP Mail (No SMTP/IMAP)

## Overview

HTTP Mail provides disposable, in-memory messaging over plain HTTP routes. It is designed for low-friction delivery without external SMTP/IMAP infrastructure.

Core model:

- **Mailbox address** (public): can be shared with senders
- **Read key** (private): required to read/delete/destroy mailbox content
- **Default deny**: no read key, no inbox access
- **In-memory only**: no mailbox messages are persisted to disk
- **Auto-expiry**: messages expire after 24 hours

## Route Summary

All routes are under `/{path}/mail`.

- `GET /{path}/mail`  
  Open the HTTP Mail UI.

- `POST /{path}/mail/new`  
  Create mailbox, returning JSON with:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

- `POST /{path}/mail/{address}/send`  
  Send to a mailbox by path address.

- `POST /{path}/mail/send`  
  Send using form/json-provided address:
  - form field: `_address_override`
  - JSON field: `address`

- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Read inbox (read key required).

- `POST /{path}/mail/{address}/delete/{message_id}`  
  Delete one message (read key required).

- `POST /{path}/mail/{address}/destroy`  
  Destroy mailbox and wipe all messages (read key required).

## Security Behavior

- Mailbox read access is protected by constant-time key comparison.
- Message content is overwritten in memory before deletion.
- Destroying a mailbox:
  - removes it from global lookup immediately,
  - marks it destroyed under mailbox lock,
  - wipes and clears message list.
- Writes to destroyed mailboxes are rejected.

## JavaScript and No-JS Support

The UI supports both modes:

- JavaScript mode uses JSON APIs directly.
- No-JS mode can send messages through `POST /{path}/mail/send` using `_address_override`.

## Quick Example (JSON)

1) Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

2) Send message:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'
```

3) Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

