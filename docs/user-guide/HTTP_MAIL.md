# HTTP Mail Guide

## Overview

HTTP Mail provides short-lived, in-memory messaging over HTTP without SMTP or IMAP.
Each mailbox has:

- **address**: safe to share with senders
- **read key**: private secret required to read and delete messages

Default behavior is deny-by-default: inbox reads fail without the exact read key.

## Security model

- No SMTP or IMAP dependencies
- Messages are stored in memory only
- Message bodies are length-limited and sanitized
- Messages expire automatically after 24 hours
- Deletion overwrites message content in memory before removal
- Mailboxes can be destroyed, which scrubs stored messages

## Typical flow

1. Create mailbox: `POST /<path>/mail/new`
2. Share mailbox address with sender
3. Sender posts message
4. Owner reads inbox with `?key=<read_key>`
5. Owner deletes messages or destroys mailbox

## API endpoints

### `GET /<path>/mail`
Renders the HTTP Mail UI.

### `POST /<path>/mail/new`
Creates a mailbox and returns:

- `address`
- `read_key`
- `send_url`
- `inbox_url`

### `POST /<path>/mail/send` (new)
Sends a message when address is in payload.

Supported payload fields:

- `address` (or `_address_override`)
- `subject`
- `body` (required)
- `sender`

This endpoint is useful for:

- no-JavaScript form flows
- API clients that prefer stable endpoint URLs

### `POST /<path>/mail/<address>/send`
Sends a message directly to an address in the URL.

### `GET /<path>/mail/<address>/inbox?key=<read_key>`
Reads inbox content with the correct read key.

### `POST /<path>/mail/<address>/delete/<msg_id>`
Deletes one message (requires `read_key`).

### `POST /<path>/mail/<address>/destroy`
Destroys mailbox and scrubs all stored messages (requires `read_key`).

## Example (JSON send with payload-address endpoint)

```bash
curl -X POST "http://localhost:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "MAILBOX_ADDRESS",
    "subject": "hello",
    "body": "message body",
    "sender": "alice"
  }'
```

