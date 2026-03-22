# HTTP Mail User Guide

## Overview

HTTP Mail provides mailbox-style messaging over plain HTTP with no SMTP/IMAP dependency.
Each mailbox has:

- `address` (public): share with senders
- `read_key` (private): required to read/delete/rotate access

Messages are stored in memory only and expire automatically after 24 hours.

## Core Security Model

- Default deny: inbox reads require the correct `read_key`
- Random high-entropy keys generated with `secrets.token_urlsafe`
- Message content overwritten in memory before deletion
- Entire mailbox can be destroyed, which clears all stored messages

## Endpoints

All routes are scoped under `/<path>/mail`.

- `GET /<path>/mail` - HTTP Mail UI
- `POST /<path>/mail/new` - Create mailbox
- `POST /<path>/mail/<address>/send` - Send message to mailbox
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - Read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>` - Delete one message
- `POST /<path>/mail/<address>/rotate-key` - Rotate mailbox read key
- `POST /<path>/mail/<address>/destroy` - Destroy mailbox

## Typical Workflow

1. Create mailbox from the UI or via `POST /mail/new`.
2. Save both `address` and `read_key` immediately.
3. Share only the `address`.
4. Read inbox with `address + read_key`.
5. Rotate `read_key` if exposure is suspected.

## Read-Key Rotation

Read-key rotation allows mailbox owners to invalidate old read credentials without recreating the mailbox.

Behavior:

- Requires the current valid `read_key`
- Returns a newly generated `new_read_key`
- Old key stops working immediately
- Existing mailbox messages remain accessible with the new key

JSON example:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"read_key":"CURRENT_KEY"}' \
  "http://localhost/<path>/mail/<address>/rotate-key"
```

Response:

```json
{
  "success": true,
  "new_read_key": "NEW_KEY"
}
```

## Operational Notes

- If a mailbox is destroyed, further writes are rejected.
- HTTP Mail is in-memory only; data is not persisted across restart.
- Keep `read_key` out of logs, screenshots, and shared links.
