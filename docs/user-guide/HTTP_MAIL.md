# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over plain HTTP with no SMTP/IMAP dependencies.

## Key Model

- **Mailbox address**: short public token you can share with senders
- **Read key**: private secret required to read/delete/destroy mailbox content
- **Default deny**: without the read key, inbox access is rejected
- **In-memory only**: messages are never persisted to disk

## Endpoints

All endpoints are under `/<path>/mail/...`:

- `GET /mail` - HTTP Mail UI
- `POST /mail/new` - create mailbox (returns `address` and `read_key`)
- `POST /mail/<address>/send` - send message to a known mailbox address
- `POST /mail/send` - no-JS fallback send route (address supplied in form/json body)
- `GET /mail/<address>/inbox?key=<read_key>` - read mailbox messages
- `GET /mail/<address>/stats?key=<read_key>` - mailbox metadata/stats
- `POST /mail/<address>/delete/<msg_id>` - delete one message
- `POST /mail/<address>/destroy` - destroy entire mailbox

## Mailbox Stats API

`GET /<path>/mail/<address>/stats?key=<read_key>`

Example JSON response:

```json
{
  "address": "AbCdEfGhIjKl",
  "created_at": "2026-03-23T12:34:56.123456",
  "message_count": 2,
  "oldest_message_at": "2026-03-23T12:35:01.000000",
  "newest_message_at": "2026-03-23T12:40:22.000000",
  "expiry_hours": 24,
  "destroyed": false
}
```

## Security and Lifecycle Notes

- Messages are capped at 2000 characters and sanitized.
- Message content is overwritten in memory before deletion/expiry.
- Destroyed mailboxes reject late writes from stale references.
- HTTP Mail UI now uses external JS/CSS assets (`static/http_mail.js`, `static/http_mail.css`)
  so it works under strict CSP (`script-src 'self'`, `style-src 'self'`).

## Quick Manual Test

1. Open `/<path>/mail`
2. Create a mailbox and copy address/read key
3. Send a message using either:
   - Send form (no-JS fallback uses `/mail/send`)
   - Direct endpoint: `POST /<path>/mail/<address>/send`
4. Open inbox with read key
5. Click **Mailbox Stats** to fetch metadata
