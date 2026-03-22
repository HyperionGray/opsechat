# HTTP Mail Guide

HTTP Mail provides an inbox-like workflow over plain HTTP without SMTP/IMAP.

- Create a mailbox and receive:
  - a public `address` (share with senders)
  - a private `read_key` (required to read/delete/destroy)
- Senders can post messages to the mailbox `address`.
- Readers must present the correct `read_key`.
- Messages are in-memory only and expire automatically after 24 hours.

## Endpoints

All routes are scoped under your app path:

- `GET /<path>/mail` - UI
- `POST /<path>/mail/new` - create mailbox
- `POST /<path>/mail/<address>/send` - send message
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - read inbox
- `POST /<path>/mail/<address>/delete/<msg_id>` - delete one message
- `POST /<path>/mail/<address>/destroy` - destroy mailbox

## JSON inbox pagination

`GET /<path>/mail/<address>/inbox?key=<read_key>` supports optional query params:

- `limit` (optional): integer `1-200`
- `offset` (optional): integer `>= 0`, default `0`
- `order` (optional): `asc` (oldest first) or `desc` (newest first), default `asc`

Example:

```bash
curl -H "Accept: application/json" \
  "http://127.0.0.1:5000/<path>/mail/<address>/inbox?key=<read_key>&order=desc&limit=20&offset=0"
```

JSON response includes:

- `messages`
- `total_messages`
- `returned_messages`
- `offset`
- `limit`
- `order`
- `has_more`

Invalid pagination values return HTTP `400` with a JSON `error`.
