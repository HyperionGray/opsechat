# HTTP Mail User Guide

## Overview

HTTP Mail provides an inbox model over plain HTTP without SMTP/IMAP dependencies.
Each mailbox has:

- a public `address` (shareable with senders)
- a private `read_key` (required to read/delete/destroy)

Messages are in-memory only and expire automatically after 24 hours.

## Core Endpoints

- `GET /{path}/mail` - HTTP Mail UI
- `POST /{path}/mail/new` - Create mailbox (`address`, `read_key`)
- `POST /{path}/mail/{address}/send` - Send message to a mailbox
- `POST /{path}/mail/send` - No-JS compose fallback using form field `_address_override`
- `GET /{path}/mail/{address}/inbox?key={read_key}` - Read inbox
- `POST /{path}/mail/{address}/delete/{msg_id}` - Delete one message
- `POST /{path}/mail/{address}/destroy` - Destroy mailbox and wipe messages

## No-JavaScript Flow

The compose form supports non-JavaScript browsers:

1. Open `/{path}/mail`
2. Switch to **Send a Message**
3. Enter recipient address, subject/body, sender
4. Submit form to `POST /{path}/mail/send`

The server routes the form to the target mailbox using `_address_override`.

## Security and Error Semantics

- Default deny: inbox reads require exact `read_key`
- Destroyed mailbox writes are rejected
- If a send races with mailbox destruction, send can return `410 Gone`
- Missing address on no-JS fallback returns `400 Bad Request`
- Unknown mailbox returns `404 Not Found`

## cURL Examples

Create mailbox:

```bash
curl -X POST "http://localhost:5001/{path}/mail/new"
```

Send message (JSON API):

```bash
curl -X POST "http://localhost:5001/{path}/mail/{address}/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hi","body":"hello","sender":"alice"}'
```

Read inbox:

```bash
curl "http://localhost:5001/{path}/mail/{address}/inbox?key={read_key}" \
  -H "Accept: application/json"
```
