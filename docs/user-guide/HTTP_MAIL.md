# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over plain HTTP with no SMTP/IMAP dependency.
It is designed for ephemeral, in-memory operation:

- Mailboxes are random addresses
- Reading requires a private `read_key`
- Messages expire automatically after 24 hours
- Data is never written to disk by this subsystem

## Core Security Model

Each mailbox has two tokens:

1. `address` (public): share with senders
2. `read_key` (private): required to read/delete/destroy

Without a valid `read_key`, inbox data is denied.

## Endpoints

All routes are prefixed with `/<path>/mail`.

### Create mailbox

- Method: `POST`
- Route: `/new`
- Response:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

### Send message (JSON/API)

- Method: `POST`
- Route: `/<address>/send`
- Body (JSON):
  - `subject` (optional)
  - `body` (required)
  - `sender` (optional)

### Send message (non-JS form fallback)

- Method: `POST`
- Route: `/send`
- Form fields:
  - `_address_override` (required mailbox address)
  - `subject`
  - `body`
  - `sender`

This route exists for environments that disable JavaScript.

### Read inbox

- Method: `GET`
- Route: `/<address>/inbox`
- Query:
  - `key` (required)

For JSON clients, the inbox endpoint also supports:

- `limit` (default `50`, max `200`)
- `offset` (default `0`)
- `include_body` (`true`/`false`, default `true`)
- `order` (`oldest` or `newest`, default `oldest`)

JSON response includes:

- `messages`
- `total_messages`
- `limit`
- `offset`
- `has_more`

### Mailbox status (metadata only)

- Method: `GET`
- Route: `/<address>/status`
- Query:
  - `key` (required)

Returns mailbox metadata without message bodies:

- `message_count`
- `created_at`
- `oldest_message_at`
- `newest_message_at`
- `destroyed`

### Delete one message

- Method: `POST`
- Route: `/<address>/delete/<msg_id>`
- Requires `read_key` in JSON body or form body

### Destroy mailbox

- Method: `POST`
- Route: `/<address>/destroy`
- Requires `read_key` in JSON body or form body
- Overwrites message memory before deletion

## Example API Flow

1. Create mailbox:

```bash
curl -s -X POST http://localhost:5000/SEC_PATH/mail/new
```

2. Send message:

```bash
curl -s -X POST \
  http://localhost:5000/SEC_PATH/mail/ADDRESS/send \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test","sender":"alice"}'
```

3. Read inbox with pagination:

```bash
curl -s \
  "http://localhost:5000/SEC_PATH/mail/ADDRESS/inbox?key=READ_KEY&limit=20&offset=0&include_body=false&order=newest" \
  -H "Accept: application/json"
```

4. Read mailbox status:

```bash
curl -s \
  "http://localhost:5000/SEC_PATH/mail/ADDRESS/status?key=READ_KEY" \
  -H "Accept: application/json"
```
