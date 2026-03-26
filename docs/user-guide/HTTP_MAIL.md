# HTTP Mail (Email over HTTP)

HTTP Mail is a lightweight, in-memory mailbox system that avoids SMTP/IMAP entirely.
It is useful when you want disposable, default-deny message drops over your existing
OpSecChat endpoint.

## Security model

- Each mailbox has:
  - `address` (public): share this with senders
  - `read_key` (private): required to read mailbox contents and metadata
- Default deny: without `read_key`, inbox and status are inaccessible
- Messages are plain text and sanitized
- Messages auto-expire after 24 hours
- Message/mailbox deletion overwrites content in memory before removal
- Mailbox writes are rejected once a mailbox is destroyed

## Routes

All routes are namespaced under `/{path}/mail`.

- `GET /{path}/mail`
  - HTTP Mail UI (create mailbox, compose, read inbox)

- `POST /{path}/mail/new`
  - Create mailbox
  - Response JSON includes:
    - `address`
    - `read_key`
    - `send_url`
    - `inbox_url`

- `POST /{path}/mail/{address}/send`
  - Send a message to mailbox by address
  - No auth required for senders

- `POST /{path}/mail/send`
  - Form/no-JS sender route
  - Requires `_address_override` form field

- `GET /{path}/mail/{address}/status?key={read_key}`
  - Returns mailbox metadata for owner only
  - Fields:
    - `address`
    - `created_at`
    - `message_count`
    - `destroyed`
    - `expires_after_hours`
    - `max_message_length`

- `GET /{path}/mail/{address}/inbox?key={read_key}`
  - Read messages (owner only)

- `POST /{path}/mail/{address}/delete/{msg_id}`
  - Delete message (requires `read_key`)

- `POST /{path}/mail/{address}/destroy`
  - Destroy mailbox (requires `read_key`)

## Error semantics

- `404` mailbox not found
- `403` invalid `read_key`
- `410` mailbox unavailable (existed but was destroyed before write commit)
- `400` invalid sender input (for example, missing body or missing address in no-JS send)

## Minimal API flow

1) Create mailbox:

```bash
curl -X POST "http://localhost:5000/<path>/mail/new" -H "Accept: application/json"
```

2) Send message:

```bash
curl -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"anon"}'
```

3) Check mailbox status:

```bash
curl "http://localhost:5000/<path>/mail/<address>/status?key=<read_key>"
```

4) Read inbox:

```bash
curl "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```
