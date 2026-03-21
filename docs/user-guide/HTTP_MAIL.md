# HTTP Mail Guide

## Overview

HTTP Mail provides an email-like workflow without SMTP/IMAP dependencies.
Messages stay in-memory and are accessed with a mailbox address + private read key.

Key properties:

- Default-deny inbox reads (read key required)
- In-memory storage only
- Message expiry after 24 hours
- Message overwrite before delete/destroy

## Routes

All routes are under `/{path}/mail`.

- `GET /{path}/mail` - UI
- `POST /{path}/mail/new` - create mailbox
- `POST /{path}/mail/send` - generic sender endpoint (address passed in body)
- `POST /{path}/mail/<address>/send` - direct sender endpoint
- `GET /{path}/mail/<address>/inbox?key=<read_key>` - inbox read
- `POST /{path}/mail/<address>/delete/<msg_id>` - delete one message
- `POST /{path}/mail/<address>/destroy` - destroy entire mailbox

## New Inbox Query Features

The inbox endpoint now supports lightweight mailbox querying:

- `q` - text search across subject, body, and sender
- `sender` - exact sender handle filter (case-insensitive)
- `limit` - max messages returned (clamped to 1..200)
- `order` - `asc` (oldest first) or `desc` (newest first)

Example:

```text
GET /{path}/mail/<address>/inbox?key=<read_key>&q=alert&sender=alice&limit=20&order=desc
```

JSON responses include a `filters` object so clients can confirm effective query state.

## Generic Send Endpoint

For form-based usage and shareable tooling, `POST /{path}/mail/send` accepts:

- `_address_override` (form field) or `address` (JSON)
- `subject`
- `body` (required)
- `sender` (optional, defaults to `anonymous`)

This avoids requiring callers to build a dynamic URL per-address.

## Concurrency Hardening

Mailbox destruction now marks a mailbox as destroyed under lock.
Any stale references held by concurrent writers will refuse new writes, returning a send failure instead of recreating data after destruction.
