# HTTP Mail User Guide

## Overview

HTTP Mail provides inbox-style messaging without SMTP or IMAP. A mailbox is identified by:

- **Address**: public token that senders can use
- **Read key**: private token required to read, delete, or destroy mailbox data

Messages are stored in memory only and expire automatically.

## Security and Storage Model

- Default-deny inbox access (read key required)
- In-memory storage only (no disk persistence)
- Message content overwritten before deletion
- 24-hour message expiry
- Mailbox destruction scrubs remaining in-memory messages

## Limits

- **Message body limit**: 2000 characters
- **Mailbox capacity**: 200 active messages per mailbox

When a mailbox is full, send attempts are rejected with HTTP `429`.

## Endpoints

All routes are mounted under `/{path}/mail`.

- `POST /new`  
  Create mailbox; returns `address`, `read_key`, and helper URLs.

- `POST /{address}/send`  
  Send message (subject/body/sender). No auth required to send.

- `GET /{address}/inbox?key={read_key}`  
  Read messages (JSON if `Accept: application/json`).

- `GET /{address}/meta?key={read_key}`  
  Return mailbox metadata:
  - address and creation timestamp
  - current `message_count`
  - `max_messages`
  - `max_message_length`
  - expiry policy (`expiry_hours`)
  - oldest/newest message timestamps

- `POST /{address}/delete/{msg_id}`  
  Delete one message (requires read key).

- `POST /{address}/destroy`  
  Destroy mailbox and overwrite in-memory message data.

## Quick Example

```bash
# Create mailbox
curl -s -X POST http://localhost:5001/<path>/mail/new

# Send message
curl -s -X POST http://localhost:5001/<path>/mail/<address>/send \
  -H "Content-Type: application/json" \
  -d '{"subject":"hi","body":"hello","sender":"alice"}'

# Read metadata
curl -s "http://localhost:5001/<path>/mail/<address>/meta?key=<read_key>"
```
