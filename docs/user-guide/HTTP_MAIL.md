# HTTP Mail (No SMTP/IMAP)

## Overview

HTTP Mail is a lightweight inbox model built for anonymous drop-style messaging.
It does not require SMTP, IMAP, or account registration.

Each mailbox has:
- **Address** (public): share with senders
- **Read key** (secret): required to read/delete/destroy mailbox content

Default-deny behavior applies at read time. Without the read key, inbox access fails.

## Routes

All routes are mounted under `/{path}/mail`.

- `GET /{path}/mail`
  - Main HTTP Mail UI
- `POST /{path}/mail/new`
  - Create mailbox
  - Returns `address` and `read_key`
- `POST /{path}/mail/send`
  - Generic send endpoint (useful for no-JS form posts)
  - Accepts address in payload
- `POST /{path}/mail/{address}/send`
  - Direct send endpoint where address is in URL
- `GET /{path}/mail/{address}/inbox?key=<read_key>`
  - Read inbox (requires read key)
- `POST /{path}/mail/{address}/delete/{msg_id}`
  - Delete single message (requires read key)
- `POST /{path}/mail/{address}/destroy`
  - Destroy mailbox and wipe messages (requires read key)

## Message Handling

- Message max length: **2000 characters**
- Subject max length: **200 characters**
- Sender handle max length: **64 characters**
- Messages expire after **24 hours**
- Mailboxes with no messages can be cleaned up after **48 hours**
- Deletion/destroy operations overwrite message contents in memory before removal

## Lifecycle Safety

Mailbox destruction is race-safe:
- Mailbox is removed from global lookup first
- Messages are overwritten and cleared under mailbox lock
- Mailbox is marked destroyed, and stale references reject late writes

## Usage Example (JSON)

```bash
# 1) create mailbox
curl -s -X POST http://localhost:5000/<path>/mail/new

# 2) send message
curl -s -X POST http://localhost:5000/<path>/mail/send \
  -H 'Content-Type: application/json' \
  -d '{"address":"<address>","subject":"hello","body":"test","sender":"anon"}'

# 3) read inbox
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H 'Accept: application/json'
```
