# HTTP Mail (Email over HTTP)

## Overview

HTTP Mail provides a lightweight mailbox system over standard HTTP routes with no SMTP/IMAP dependency.

- Public mailbox address for receiving messages
- Private read key for inbox access (default deny)
- In-memory storage only (no disk persistence)
- 24-hour automatic message expiry
- Secure overwrite of message content before deletion

## Core Security Model

1. Create a mailbox to receive:
   - `address` (shareable with senders)
   - `read_key` (secret; required to read/delete/destroy)
2. Anyone with the address can send a message.
3. Only holders of the read key can read inbox contents.
4. Destroyed mailboxes are permanently invalidated.

## Mailbox Lifecycle Guarantees

Recent hardening introduced strict destruction semantics:

- A mailbox is marked as destroyed under lock before it is removed from storage.
- Any stale mailbox references can no longer accept writes.
- Attempts to send to a destroyed mailbox reference return HTTP `410 Gone`.

This closes a race where a sender could post during mailbox teardown and create inaccessible orphaned messages.

## API Endpoints

All routes are mounted under `/{path}/mail`:

- `GET /{path}/mail` - HTTP Mail UI
- `POST /{path}/mail/new` - Create mailbox
- `POST /{path}/mail/{address}/send` - Send message
- `GET /{path}/mail/{address}/inbox?key={read_key}` - Read inbox
- `POST /{path}/mail/{address}/delete/{msg_id}` - Delete one message
- `POST /{path}/mail/{address}/destroy` - Destroy mailbox

## Notes for Operators

- Read keys are shown once during mailbox creation; users should store them safely.
- Destroying a mailbox is irreversible.
- Message retention is intentionally short-lived and memory-only.
