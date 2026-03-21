# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over plain HTTP without SMTP/IMAP.

It is designed for temporary, low-friction message dropboxes:

- Public mailbox address for senders
- Private `read_key` for inbox reads/deletes
- In-memory storage only
- Automatic expiry and overwrite on deletion

## Security model

1. Mailbox creation returns:
   - `address` (share with senders)
   - `read_key` (owner secret)
2. Anyone with `address` can send messages.
3. Only `read_key` can:
   - read inbox contents
   - delete messages
   - destroy the entire mailbox
4. Destroyed mailboxes are scrubbed in memory and reject future writes.

## API routes

All routes are under `/<path>/mail`.

- `GET /<path>/mail`
  - Render the HTTP Mail page
- `POST /<path>/mail/new`
  - Create mailbox
  - Returns JSON: `address`, `read_key`, `send_url`, `inbox_url`
- `POST /<path>/mail/<address>/send`
  - Send message to mailbox
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Read inbox (requires valid read key)
- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Delete one message (requires `read_key`)
- `POST /<path>/mail/<address>/destroy`
  - Destroy mailbox and scrub content (requires `read_key`)

## Mailbox lifecycle details

- Messages expire after 24 hours.
- Expired messages are overwritten in memory before removal.
- Destroying a mailbox:
  - removes it from global lookup,
  - marks mailbox state as destroyed,
  - overwrites and clears all stored messages.
- If a stale mailbox reference attempts to write after destruction, write is rejected.

## Common status codes

- `200` success
- `400` invalid payload (for example, empty message body)
- `403` invalid or missing `read_key`
- `404` mailbox not found
- `410` mailbox was destroyed and no longer accepts writes

## Quick JSON flow

Create mailbox:

```bash
curl -X POST http://127.0.0.1:5000/<path>/mail/new
```

Send:

```bash
curl -X POST http://127.0.0.1:5000/<path>/mail/<address>/send \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"anon"}'
```

Read:

```bash
curl -H "Accept: application/json" \
  "http://127.0.0.1:5000/<path>/mail/<address>/inbox?key=<read_key>"
```
