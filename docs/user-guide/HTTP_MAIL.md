# HTTP Mail Guide

HTTP Mail provides an email-like workflow over plain HTTP with no SMTP/IMAP dependencies.
It is designed for short-lived, in-memory messaging where the mailbox owner controls read access
with a private key.

## Security Model

- Each mailbox has:
  - **address** (public): safe to share with senders
  - **read key** (private): required to read inbox content
- Anyone with the address can send messages.
- Only holders of the read key can read, delete, or destroy mailbox content.
- Messages expire automatically after 24 hours.
- Data is kept in memory only.

## Routes

All routes are under:

`/<random_path>/mail`

- `GET /<path>/mail` - Main HTTP Mail UI
- `POST /<path>/mail/new` - Create mailbox
- `POST /<path>/mail/<address>/send` - Send a message
- `GET /<path>/mail/<address>/inbox?key=<read_key>` - Read inbox
- `GET /<path>/mail/<address>/stats?key=<read_key>` - Mailbox metadata
- `POST /<path>/mail/<address>/delete/<msg_id>` - Delete one message
- `POST /<path>/mail/<address>/destroy` - Destroy mailbox and all messages

## New Inbox Query Options

The inbox endpoint now supports optional query controls:

- `limit` (integer, `1..500`): return only the newest N messages
- `sender` (string): exact sender-handle match (case-insensitive)

Examples:

```text
GET /<path>/mail/<address>/inbox?key=<read_key>&limit=20
GET /<path>/mail/<address>/inbox?key=<read_key>&sender=alice
GET /<path>/mail/<address>/inbox?key=<read_key>&limit=10&sender=alice
```

If `limit` is invalid, the server returns HTTP `400`.

## Mailbox Stats API

`GET /<path>/mail/<address>/stats?key=<read_key>`

Response fields:

- `address`
- `message_count`
- `created_at`
- `oldest_message_at`
- `newest_message_at`

This endpoint is useful for lightweight polling without downloading full message bodies.

