# HTTP Mail (Email over HTTP)

## Overview

HTTP Mail provides mailbox-style messaging without SMTP or IMAP. It is designed for
simple, in-memory message delivery over existing HTTP endpoints.

Each mailbox has:
- **address**: public identifier used by senders
- **read_key**: private secret required to read mailbox contents and metadata

Default access model:
- Anyone with the mailbox **address** can send a message.
- Only callers with the mailbox **read_key** can read, delete, or destroy.

Messages are stored in memory only and expire automatically after 24 hours.

## Endpoints

All routes are namespaced under:

`/<path>/mail/...`

### Create mailbox

- **POST** `/<path>/mail/new`
- Returns JSON with:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

### Send message

- **POST** `/<path>/mail/<address>/send`
- Supports JSON and form data.
- Required field: `body`
- Optional fields: `subject`, `sender`

### Read inbox

- **GET** `/<path>/mail/<address>/inbox?key=<read_key>`
- Returns messages when key is valid.
- Returns `403` when key is invalid.

### Read mailbox status (new)

- **GET** `/<path>/mail/<address>/status?key=<read_key>`
- Returns mailbox metadata (no message bodies):
  - `address`
  - `created_at`
  - `destroyed`
  - `message_count`
  - `oldest_message_at`
  - `newest_message_at`

This endpoint is intended for automation and operational checks.

### Delete one message

- **POST** `/<path>/mail/<address>/delete/<msg_id>`
- Requires `read_key` in request body/form.

### Destroy mailbox

- **POST** `/<path>/mail/<address>/destroy`
- Requires `read_key`.
- Destroys mailbox data in memory.

## Security and lifecycle notes

- Message content is overwritten in memory before deletion.
- Destroyed mailboxes reject late writes from stale references.
- Mailboxes removed from storage return `404` for future lookups.

## Quick test example

```bash
# 1) Create a mailbox
curl -s -X POST "http://localhost:5000/<path>/mail/new"

# 2) Send a message
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'

# 3) Read status (metadata only)
curl -s "http://localhost:5000/<path>/mail/<address>/status?key=<read_key>"

# 4) Read inbox
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>"
```
