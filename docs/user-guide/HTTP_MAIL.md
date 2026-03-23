# HTTP Mail Guide

## Overview

HTTP Mail provides mailbox-style messaging over HTTP without SMTP or IMAP.
It is designed for short-lived, in-memory communication:

- Public mailbox address for receiving messages
- Private read key for inbox access (default deny)
- 24-hour message expiry
- Memory overwrite before deletion

All data is in-memory only.

## Core Flow

1. Create mailbox: `POST /{path}/mail/new`
2. Share mailbox address with senders
3. Keep read key private
4. Read inbox with read key:
   `GET /{path}/mail/{address}/inbox?key={read_key}`

## Routes

- `GET /{path}/mail`  
  Main UI.

- `POST /{path}/mail/new`  
  Create mailbox, returns JSON:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

- `POST /{path}/mail/{address}/send`  
  Send to known mailbox address (JSON or form).

- `POST /{path}/mail/send`  
  Compose-form fallback for non-JavaScript flow.
  Uses form field `_address_override` (or JSON `address`).

- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Read inbox with private key.

- `POST /{path}/mail/{address}/delete/{message_id}`  
  Delete one message (requires `read_key`).

- `POST /{path}/mail/{address}/destroy`  
  Destroy entire mailbox (requires `read_key`).

## Security Behavior

- Inbox reads are denied without correct read key.
- Message and sender fields are sanitized as plain text.
- Messages older than 24 hours are expired and overwritten.
- Destroyed mailboxes reject additional writes, including stale references.

## Example (JSON)

Create mailbox:

```bash
curl -X POST "http://localhost:5000/<path>/mail/new"
```

Send message:

```bash
curl -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"Hello","body":"Test message","sender":"alice"}'
```

Read inbox:

```bash
curl "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```
