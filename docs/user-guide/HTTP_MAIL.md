# HTTP Mail Guide

## Overview

HTTP Mail is an in-memory mailbox system that works without SMTP/IMAP. A mailbox is identified by:

- **address**: public identifier that senders can use
- **read key**: private secret required to read/delete/rotate mailbox access

Data is not persisted to disk. Messages expire automatically after 24 hours.

## Security Model

- Default deny: inbox reads require a valid read key
- Message content is overwritten before deletion
- Mailbox destruction overwrites queued messages and blocks stale writers
- Destroyed mailboxes return `410 Gone` when a stale reference attempts to write

## Routes

All routes are scoped under `/<path>/mail`.

- `GET /<path>/mail`
  - Main HTTP Mail UI
- `POST /<path>/mail/new`
  - Create mailbox, returns `address` and `read_key`
- `POST /<path>/mail/send`
  - No-JS form fallback, expects `_address_override`
- `POST /<path>/mail/<address>/send`
  - Send message to mailbox
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Read inbox
- `POST /<path>/mail/<address>/delete/<id>`
  - Delete one message (requires read key)
- `POST /<path>/mail/<address>/destroy`
  - Destroy mailbox and scrub remaining messages (requires read key)
- `POST /<path>/mail/<address>/rotate-key`
  - Rotate read key and invalidate the previous key immediately

## Example JSON Flow

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Send message:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"anon"}'
```

Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

Rotate read key:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/rotate-key" \
  -H "Content-Type: application/json" \
  -d '{"read_key":"<read_key>"}'
```
