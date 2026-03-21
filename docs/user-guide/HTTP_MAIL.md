# HTTP Mail Guide

## Overview

HTTP Mail is an in-memory mailbox system for OpSecChat that does not depend on SMTP or IMAP.
Each mailbox has:

- A public `address` (safe to share with senders)
- A private `read_key` (required to read and manage inbox data)

Default-deny access is enforced for inbox reads and mailbox management. Messages expire after
24 hours and are overwritten in memory before deletion.

## Core Security Properties

- No account is required to send to a mailbox address
- Inbox reads require a valid `read_key`
- Message and mailbox deletion overwrite message content before removal
- Mailboxes can rotate read keys if a key may have leaked
- Destroyed mailboxes reject future writes

## Routes

All routes are namespaced under `/{path}/mail`:

- `GET /{path}/mail`
  - HTTP Mail web UI
- `POST /{path}/mail/new`
  - Create mailbox, returns `address` and `read_key`
- `POST /{path}/mail/send`
  - Send message using payload/form address field
- `POST /{path}/mail/<address>/send`
  - Send message directly to a mailbox address
- `GET /{path}/mail/<address>/inbox?key=<read_key>`
  - Read mailbox contents (default deny without valid key)
- `POST /{path}/mail/<address>/delete/<msg_id>`
  - Delete one message (requires `read_key`)
- `POST /{path}/mail/<address>/rotate-key`
  - Rotate mailbox read key (requires current `read_key`)
- `POST /{path}/mail/<address>/destroy`
  - Destroy mailbox and scrub in-memory message content

## Read-Key Rotation

Read-key rotation lets mailbox owners revoke an exposed key without creating a new mailbox.

Behavior:

1. Client submits current `read_key` to `POST /{path}/mail/<address>/rotate-key`
2. Server validates key and generates a replacement key
3. Previous key stops working immediately
4. New key must be stored by the user

## Example JSON Flow

Create mailbox:

```bash
curl -s -X POST "http://127.0.0.1:5000/<path>/mail/new"
```

Send message:

```bash
curl -s -X POST "http://127.0.0.1:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'
```

Rotate key:

```bash
curl -s -X POST "http://127.0.0.1:5000/<path>/mail/<address>/rotate-key" \
  -H "Content-Type: application/json" \
  -d '{"read_key":"<current_key>"}'
```

Read inbox:

```bash
curl -s "http://127.0.0.1:5000/<path>/mail/<address>/inbox?key=<read_key>"
```

