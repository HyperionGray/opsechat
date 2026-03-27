# HTTP Mail Guide

## Overview

HTTP Mail is an in-memory mailbox system that works over plain HTTP routes.
It does not require SMTP or IMAP, and it uses a default-deny read model:

- Public mailbox address: safe to share with senders
- Private read key: required to read mailbox data

All messages are in memory only and expire automatically.

## Security Model

- Anyone with a mailbox address can send messages to that mailbox.
- Reading mailbox contents requires the correct read key.
- Message and mailbox deletion overwrites message data in memory before removal.
- Mailboxes are marked destroyed during deletion so in-flight writes are rejected.

## Routes

All routes are under:

`/<path>/mail`

### Main UI

- `GET /<path>/mail`
  - Renders mailbox UI (create, send, read).

### Create mailbox

- `POST /<path>/mail/new`
  - Returns JSON:
    - `address`
    - `read_key`
    - `send_url`
    - `inbox_url`

### Send message

- `POST /<path>/mail/<address>/send`
  - JSON or form payload accepted.
- `POST /<path>/mail/send`
  - Form fallback route (uses `_address_override` field).

Required fields:

- `body` (required)
- `subject` (optional)
- `sender` (optional, defaults to `anonymous`)

### Read mailbox status metadata

- `GET /<path>/mail/<address>/status?key=<read_key>`
  - Returns mailbox metadata when key is valid:
    - `address`
    - `created_at`
    - `message_count`
    - `latest_message_at`

### Read inbox

- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Returns messages (JSON if `Accept: application/json`).

### Delete message

- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Requires `read_key` in JSON or form body.

### Destroy mailbox

- `POST /<path>/mail/<address>/destroy`
  - Requires `read_key` in JSON or form body.
  - Removes mailbox from storage and scrubs message data in memory.

## Testing

Run HTTP mail tests:

```bash
PYTHONPATH=. pytest tests/test_http_mail.py -v
```

