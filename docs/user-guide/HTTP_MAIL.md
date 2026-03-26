# HTTP Mail Guide

## Overview

HTTP Mail is a lightweight mailbox system built directly into OpSecChat.
It provides email-like messaging over HTTP without SMTP/IMAP dependencies.

Key model:
- Public mailbox `address`: safe to share with senders
- Private `read_key`: required to read, delete, rotate keys, or destroy mailbox
- Default deny: no `read_key`, no inbox access
- In-memory only: nothing persisted to disk
- Message expiry: messages older than 24 hours are automatically removed

Access path:
- `/{path}/mail`

## Core Flows

### 1) Create mailbox

- Open `/{path}/mail`
- Click "Create Mailbox"
- Save:
  - Mailbox address
  - Read key

The read key is a secret credential. Treat it like a password.

### 2) Send message

Senders only need mailbox address.

Two supported paths:
- JavaScript flow: `POST /{path}/mail/<address>/send`
- No-JS fallback form: `POST /{path}/mail/send` with `_address_override`

### 3) Read inbox

- `GET /{path}/mail/<address>/inbox?key=<read_key>`
- Without the correct key, the route returns 403.

### 4) Rotate read key

If key compromise is suspected, rotate without destroying mailbox or losing messages.

- JSON/API:
  - `POST /{path}/mail/<address>/rotate-key`
  - body: `{"read_key":"<current_key>"}`
  - response: `{"success": true, "new_read_key": "..."}`
- Form/UI:
  - same route, `read_key` in form body

After rotation:
- old key is invalid
- new key grants access to existing messages

### 5) Delete message / destroy mailbox

- Delete one message:
  - `POST /{path}/mail/<address>/delete/<msg_id>` with `read_key`
- Destroy mailbox:
  - `POST /{path}/mail/<address>/destroy` with `read_key`

Destroy operation securely overwrites message content in memory before cleanup.

## Security Notes

- Read keys are generated with cryptographic randomness.
- Key comparisons use constant-time checks.
- Destroyed mailboxes reject new writes.
- Message and mailbox deletion paths perform in-memory overwrite before release.

## Minimal API Reference

- `POST /{path}/mail/new`
- `POST /{path}/mail/send` (no-JS fallback)
- `POST /{path}/mail/<address>/send`
- `GET  /{path}/mail/<address>/inbox?key=<read_key>`
- `POST /{path}/mail/<address>/rotate-key`
- `POST /{path}/mail/<address>/delete/<msg_id>`
- `POST /{path}/mail/<address>/destroy`
