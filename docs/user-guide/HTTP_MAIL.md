# HTTP Mail (Email over HTTP)

## Overview

HTTP Mail is a lightweight, in-memory mailbox system that works without SMTP or IMAP.
It is designed for temporary message exchange where the receiver controls read access
using a private key.

Core model:

- **Mailbox address**: short public identifier, safe to share with senders
- **Read key**: private secret required to read/delete/destroy mailbox content
- **Default deny**: without the read key, inbox access is denied
- **In-memory only**: no persistent mailbox storage on disk

## Security properties

- Message bodies and metadata are sanitized for plain-text rendering
- Mailbox reads use key verification (`compare_digest`)
- Messages expire automatically after 24 hours
- Message content is overwritten in memory before deletion
- Destroyed mailboxes are scrubbed and reject late writes

## Quick start

1. Open `/{path}/mail`
2. Create a mailbox
3. Save:
   - mailbox `address`
   - mailbox `read_key`
4. Share only the `address` with senders
5. Use `address + read_key` to open inbox

## HTTP endpoints

- `GET /{path}/mail`  
  Main UI

- `POST /{path}/mail/new`  
  Create mailbox (returns address + read key)

- `POST /{path}/mail/{address}/send`  
  Send a message to mailbox address

- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Read messages (JSON or HTML)

- `POST /{path}/mail/{address}/delete/{msg_id}`  
  Delete message (requires `read_key`)

- `POST /{path}/mail/{address}/destroy`  
  Destroy mailbox and scrub all messages (requires `read_key`)

## Lifecycle notes

- After mailbox destruction, the mailbox is removed from storage and messages are
  overwritten and cleared.
- If a concurrent sender holds a stale mailbox reference, writes are rejected and the
  route returns **HTTP 410 Gone**.
