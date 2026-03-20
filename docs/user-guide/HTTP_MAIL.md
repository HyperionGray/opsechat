# HTTP Mail Guide

## Overview

HTTP Mail provides an inbox-like workflow without SMTP/IMAP dependencies.
Messages are stored in memory only and are protected with a mailbox-scoped read key.

Core model:
- **Address**: shareable mailbox token that senders use.
- **Read key**: private secret required to read/delete/destroy mailbox data.
- **Expiry**: messages automatically expire after 24 hours.
- **Storage**: in-memory only; no disk persistence.

## Routes

All routes are mounted under `/{path}/mail`.

- `GET /{path}/mail`  
  Open the HTTP Mail UI.
- `POST /{path}/mail/new`  
  Create a mailbox. Returns JSON with `address` and `read_key`.
- `POST /{path}/mail/send`  
  No-JavaScript fallback send route (`_address_override` form field required).
- `POST /{path}/mail/{address}/send`  
  Send a message to a mailbox by address.
- `GET /{path}/mail/{address}/inbox?key=<read_key>`  
  Read inbox contents (default deny without valid key).
- `POST /{path}/mail/{address}/delete/{message_id}`  
  Delete one message (requires `read_key`).
- `POST /{path}/mail/{address}/destroy`  
  Destroy mailbox and all messages (requires `read_key`).

## Inbox Filters

`GET /{path}/mail/{address}/inbox` supports optional query parameters:

- `q`: case-insensitive substring search across subject/body/sender
- `sender`: case-insensitive sender substring filter
- `limit`: max messages returned (1-200)
- `sort`: `desc` (newest first, default) or `asc` (oldest first)

Example:

```text
/{path}/mail/{address}/inbox?key=<read_key>&q=alpha&sender=bob&limit=20&sort=desc
```

## Security Notes

- Reading is **default deny**: invalid/missing key returns access denied.
- Mailbox destruction marks mailbox state as destroyed to prevent late writes in race windows.
- Deleted messages are overwritten in memory before release.
- Input is treated as plain text and sanitized.
