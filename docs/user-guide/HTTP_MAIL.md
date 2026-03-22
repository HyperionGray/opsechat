# HTTP Mail Guide

HTTP Mail provides an email-like workflow over plain HTTP with **no SMTP/IMAP dependency**.
It is designed for ephemeral, in-memory operation and default-deny inbox access.

## Security Model

- Each mailbox has:
  - A **public address** (share with senders)
  - A **private read key** (required to read/delete/destroy)
- Send is open to anyone with the address.
- Read/delete/destroy requires the read key.
- Messages auto-expire after 24 hours.
- Mailbox/message data is overwritten in memory before deletion.

## Routes

All routes are namespaced under `/<path>/mail`.

### Core

- `GET /<path>/mail`  
  HTTP Mail UI.
- `POST /<path>/mail/new`  
  Create mailbox.
  - Returns JSON by default.
  - Returns HTML when `Accept: text/html` is requested (browser form flow).
- `POST /<path>/mail/<address>/send`  
  Send to a specific mailbox (JSON or form).
- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox (JSON with `Accept: application/json`, otherwise rendered HTML).
- `POST /<path>/mail/<address>/delete/<message_id>`  
  Delete message (requires `read_key` in body/form).
- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox (requires `read_key` in body/form).

### No-JavaScript Fallback Routes

- `POST /<path>/mail/send`  
  Send from HTML form using `_address_override` field.
- `GET /<path>/mail/inbox?_read_address=<addr>&_read_key=<key>`  
  Form-based inbox access; redirects to canonical inbox route.

## Curl Examples

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Send message:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test","sender":"anon"}'
```

Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```
