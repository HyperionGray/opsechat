# HTTP Mail Guide

## Overview

HTTP Mail provides ephemeral mailbox messaging over HTTP with no SMTP/IMAP dependency.
Each mailbox has:

- A public `address` (share with senders)
- A private `read_key` (required to read/delete/destroy)

Security model is default-deny: inbox access is rejected unless the correct `read_key` is provided.

## Core Properties

- In-memory only (no persistent mailbox/message storage)
- Message expiry after 24 hours
- Best-effort memory overwrite before deletion
- Mailbox destruction blocks future writes for stale references

## Routes

All routes are prefixed by `/{path}/mail`.

- `GET /{path}/mail`  
  Main HTTP Mail UI

- `POST /{path}/mail/new`  
  Create mailbox and return:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

- `POST /{path}/mail/{address}/send`  
  Send message to a mailbox (JSON or form)

- `POST /{path}/mail/send`  
  Non-JavaScript compose fallback; address is supplied in form data

- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Read inbox (requires valid read key)

- `POST /{path}/mail/{address}/delete/{msg_id}`  
  Delete one message (requires read key)

- `POST /{path}/mail/{address}/destroy`  
  Destroy mailbox and messages (requires read key)

## Response Behavior

- Invalid or missing mailbox: `404`
- Invalid read key: `403`
- Empty message body: `400`
- Send to mailbox destroyed during a race window: `410`

## Example JSON Flow

### 1) Create mailbox

```bash
curl -s -X POST http://localhost:5000/<path>/mail/new
```

### 2) Send message

```bash
curl -s -X POST http://localhost:5000/<path>/mail/<address>/send \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'
```

### 3) Read inbox

```bash
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

## Operational Notes

- Treat `read_key` like a password; never share it publicly.
- `address` is intended to be shared with senders.
- For high-risk scenarios, rotate by destroying and recreating mailboxes often.
