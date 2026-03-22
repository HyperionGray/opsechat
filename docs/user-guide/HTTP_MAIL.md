# HTTP Mail User Guide

## Overview

HTTP Mail provides ephemeral mailbox messaging over HTTP with no SMTP or IMAP dependency.
Each mailbox has:

- A public `address` that senders can use
- A private `read_key` required to read, delete, or administer mailbox contents

Messages are in-memory only and expire automatically.

## Security Model

- Default deny: inbox reads require a valid read key
- Mailbox data is not persisted to disk
- Message content is overwritten in memory on deletion or mailbox destruction
- Destroyed mailboxes reject sends from stale references

## Core Endpoints

All routes are under `/{path}/mail`.

- `GET /{path}/mail` - HTTP Mail UI
- `POST /{path}/mail/new` - Create mailbox (returns `address` and `read_key`)
- `POST /{path}/mail/<address>/send` - Send message to mailbox
- `GET /{path}/mail/<address>/inbox?key=<read_key>` - Read inbox
- `POST /{path}/mail/<address>/delete/<msg_id>` - Delete message
- `POST /{path}/mail/<address>/rotate-key` - Rotate read key
- `POST /{path}/mail/<address>/destroy` - Destroy mailbox and scrub messages

## New Feature: Read Key Rotation

Read key rotation allows mailbox owners to invalidate an exposed key without replacing the mailbox address.

Behavior:

1. Provide the current valid read key
2. Server generates and returns a new read key
3. Old key is immediately invalid

This is available in both:

- JSON API (`POST /{path}/mail/<address>/rotate-key`)
- Web UI ("Rotate Read Key" button in the read section)

## JSON Example

```json
POST /secpath/mail/aBcDeFgHiJkL/rotate-key
{
  "read_key": "current_read_key_here"
}
```

Success response:

```json
{
  "success": true,
  "read_key": "new_read_key_here"
}
```

## Operational Notes

- Save new read keys immediately after rotation
- If a read key is lost, mailbox contents cannot be recovered
- Destroy mailboxes after sensitive exchanges when possible
