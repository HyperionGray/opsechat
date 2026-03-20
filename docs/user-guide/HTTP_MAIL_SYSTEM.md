# HTTP Mail System

## Overview

HTTP Mail provides mailbox-style messaging over plain HTTP without SMTP/IMAP dependencies.

Core model:

- A mailbox has a public **address** (share with senders)
- A mailbox has a private **read key** (keep secret)
- Anyone with the address can send
- Only the read-key holder can read, delete, purge, or destroy
- Messages are in-memory only and auto-expire after 24 hours

## Endpoints

All routes are namespaced under:

`/<path>/mail`

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/<path>/mail` | HTTP Mail UI |
| `POST` | `/<path>/mail/new` | Create mailbox (returns `address` + `read_key`) |
| `POST` | `/<path>/mail/<address>/send` | Send message to mailbox |
| `GET` | `/<path>/mail/<address>/inbox?key=<read_key>` | Read inbox |
| `POST` | `/<path>/mail/<address>/delete/<msg_id>` | Delete one message |
| `POST` | `/<path>/mail/<address>/purge` | Delete all messages in mailbox |
| `POST` | `/<path>/mail/<address>/destroy` | Delete entire mailbox |

## Inbox Pagination

Inbox reads support optional pagination query parameters:

- `limit` (integer >= 1)
- `offset` (integer >= 0)

Example:

```bash
curl -H "Accept: application/json" \
  "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>&limit=20&offset=0"
```

JSON response includes:

- `messages`: paginated message slice
- `total_messages`: count of all messages currently in mailbox
- `returned`: number of messages in this response
- `limit`: requested limit (`null` if not set)
- `offset`: requested offset

## Security Notes

- Access is default-deny for inbox reads and destructive actions
- Read-key checks use constant-time comparison
- Message content is overwritten in memory before deletion
- Mailboxes with no messages can be cleaned up after 48 hours
