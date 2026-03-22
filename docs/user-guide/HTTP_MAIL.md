# HTTP Mail Guide

## Overview

HTTP Mail provides mailbox-style messaging without SMTP or IMAP. A mailbox has:

- `address`: shareable token for senders
- `read_key`: secret token required to read/manage messages

All data is in-memory only, and messages auto-expire after 24 hours.

## Security Model

- Default deny: inbox reads require the exact `read_key`
- Message content is overwritten in memory before deletion
- Destroying a mailbox securely wipes content and blocks future writes

## Routes

All routes are prefixed by `/{path}/mail`.

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Main HTTP Mail page |
| `POST` | `/new` | Create mailbox (returns address/read_key) |
| `POST` | `/<address>/send` | Send message to mailbox |
| `GET` | `/<address>/inbox?key=<read_key>` | Read inbox |
| `GET` | `/<address>/status?key=<read_key>` | Read mailbox metadata |
| `POST` | `/<address>/delete/<msg_id>` | Delete message |
| `POST` | `/<address>/destroy` | Destroy mailbox |

## API Examples

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Response:

```json
{
  "success": true,
  "address": "aBcDeFgHiJkL",
  "read_key": "veryLongSecretToken...",
  "send_url": "/<path>/mail/aBcDeFgHiJkL/send",
  "inbox_url": "/<path>/mail/aBcDeFgHiJkL/inbox"
}
```

Get mailbox status:

```bash
curl -s "http://localhost:5000/<path>/mail/aBcDeFgHiJkL/status?key=veryLongSecretToken..."
```

Response:

```json
{
  "address": "aBcDeFgHiJkL",
  "created_at": "2026-03-22T03:17:00.123456",
  "destroyed": false,
  "message_count": 2
}
```

## Notes

- If a mailbox is destroyed, API operations return `404` from storage lookups.
- During concurrent operations, stale mailbox references reject writes to prevent post-destroy message insertion.
