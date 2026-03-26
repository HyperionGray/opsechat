# HTTP Mail (Email over HTTP)

HTTP Mail is a lightweight, in-memory messaging system that avoids SMTP/IMAP.
It is designed for simple message drop-box usage where send access is public
and read access is private.

## Security model

- Each mailbox has:
  - a public `address` (safe to share with senders)
  - a private `read_key` (required for inbox access)
- Default deny: inbox reads require the exact read key.
- Messages are in-memory only (no persistence to disk).
- Messages expire after 24 hours.
- Deleted or expired messages are overwritten in memory before removal.
- Destroyed mailboxes refuse future writes.

## Endpoints

Routes are mounted under `/<path>/mail`.

- `GET /<path>/mail`
  - Main HTTP Mail UI
- `POST /<path>/mail/new`
  - Create mailbox, returns JSON `{address, read_key, send_url, inbox_url}`
- `POST /<path>/mail/send`
  - Form fallback sender route using `_address_override`
- `POST /<path>/mail/<address>/send`
  - Send message to specific mailbox (JSON or form)
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Read inbox (JSON when `Accept: application/json`)
- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Delete one message (requires `read_key`)
- `POST /<path>/mail/<address>/destroy`
  - Destroy mailbox and scrub messages (requires `read_key`)

## Quick JSON flow

1. Create mailbox:

```bash
curl -sS -X POST "http://localhost:5000/<path>/mail/new"
```

2. Send message:

```bash
curl -sS -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"anon"}'
```

3. Read inbox:

```bash
curl -sS "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

## Notes

- The `read_key` is equivalent to inbox authorization; treat it like a secret.
- If a mailbox is destroyed, subsequent sends are rejected.
