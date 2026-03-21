# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over HTTP without SMTP/IMAP dependencies.
Data is kept in memory and follows a default-deny access model.

## Core Model

- **Mailbox address**: public token that senders use
- **Read key**: private token required to read or delete mailbox content
- **In-memory only**: no mailbox or message persistence to disk
- **Auto-expiry**: messages expire after 24 hours
- **Secure deletion**: messages are overwritten before removal

## Endpoints

All routes are mounted under `/<path>/mail` where `<path>` is your runtime secret path.

- `GET /<path>/mail`  
  Main UI.

- `POST /<path>/mail/new`  
  Create mailbox. Returns JSON with `address`, `read_key`, `send_url`, and `inbox_url`.

- `POST /<path>/mail/<address>/send`  
  Send directly to a mailbox address.

- `POST /<path>/mail/send`  
  Form/JSON fallback send route. Accepts mailbox address in request body:
  - form field: `_address_override`
  - JSON field: `address`

- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox (read key required).

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message (read key required).

- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and scrub all remaining messages (read key required).

## Message Limits and Memory Safety

- Message body max length: `2000` characters
- Subject max length: `200` characters
- Sender max length: `64` characters
- Mailbox retention cap: `200` messages per mailbox
  - When the cap is reached, the oldest message is overwritten and evicted

This cap prevents unbounded mailbox growth and helps keep memory usage predictable.

## Example JSON Flow

Create mailbox:

```bash
curl -s -X POST "http://127.0.0.1:5000/<path>/mail/new"
```

Send message:

```bash
curl -s -X POST "http://127.0.0.1:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"address":"<mailbox-address>","subject":"hello","body":"test","sender":"alice"}'
```

Read inbox:

```bash
curl -s -H "Accept: application/json" \
  "http://127.0.0.1:5000/<path>/mail/<mailbox-address>/inbox?key=<read-key>"
```
