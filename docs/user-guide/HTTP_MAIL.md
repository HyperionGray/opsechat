# HTTP Mail Guide

HTTP Mail is a lightweight, in-memory mailbox system that works over plain HTTP endpoints (no SMTP/IMAP required).

It is useful when you want quick drop-style messaging with strict read access controls:

- Public mailbox address: safe to share with senders
- Private read key: required to read, delete, rotate key, or destroy mailbox
- In-memory only: nothing is written to disk
- Expiring messages: messages are removed after 24 hours

## Security model

- Default deny: inbox reads fail without a valid read key
- Keys are compared in constant time
- Message contents are overwritten in memory before deletion
- Mailbox destruction scrubs messages and rejects late writes from stale references

## UI routes

All routes are under `/<path>/mail`:

- `GET /<path>/mail`  
  Main HTTP Mail page (create mailbox, send message, read inbox)

- `POST /<path>/mail/new`  
  Create mailbox. Returns JSON with:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

- `POST /<path>/mail/send`  
  Form fallback send endpoint. Uses `_address_override` form field.

- `POST /<path>/mail/<address>/send`  
  Send to a known mailbox address (JSON or form).

- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox with read key.

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message (requires read key).

- `POST /<path>/mail/<address>/rotate-key`  
  Rotate read key (requires current read key). Old key is invalid immediately.

- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and scrub all messages (requires read key).

## Read key rotation

If a read key is exposed, rotate it immediately instead of destroying the mailbox:

1. Open inbox with current key
2. Run rotate action (`rotate-key`)
3. Save the returned `new_read_key`
4. Discard the old key

After rotation:

- old key returns `403`
- new key grants access
- existing messages remain available to the new key

## JSON examples

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Send message:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"anon"}'
```

Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

Rotate key:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/rotate-key" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"read_key":"<read_key>"}'
```

