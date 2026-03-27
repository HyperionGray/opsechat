# HTTP Mail Guide

## Overview

HTTP Mail provides email-like messaging over plain HTTP routes with no SMTP/IMAP dependency.

Each mailbox has:
- a public `address` (safe to share with senders)
- a private `read_key` (required to read and manage messages)

Default deny behavior is enforced: inbox reads fail without the correct read key.

## Routes

All routes are under `/{path}/mail`.

- `GET /{path}/mail`  
  Main UI to create a mailbox, send a message, and read inbox.
- `POST /{path}/mail/new`  
  Creates mailbox and returns JSON with `address`, `read_key`, `send_url`, and `inbox_url`.
- `POST /{path}/mail/{address}/send`  
  Sends a message to a mailbox (JSON or form).
- `POST /{path}/mail/send`  
  Non-JavaScript form fallback. Requires `_address_override` form field.
- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Reads inbox if key matches.
- `POST /{path}/mail/{address}/delete/{msg_id}`  
  Deletes one message (requires `read_key` in body/form).
- `POST /{path}/mail/{address}/destroy`  
  Destroys mailbox and securely wipes messages (requires `read_key`).

## Security Properties

- **Default deny:** wrong or missing `read_key` cannot read messages.
- **Memory only:** messages are stored in memory and expire after 24 hours.
- **Secure deletion:** message fields are overwritten before removal.
- **Mailbox destruction safety:** destroyed mailboxes reject stale writes, including stale object references.

## Non-JavaScript Compose Flow

The UI includes a fallback compose form posting to:

`POST /{path}/mail/send`

The form must include:
- `_address_override` (recipient mailbox address)
- `subject` (optional)
- `body` (required)
- `sender` (optional; defaults to `anonymous`)

If `_address_override` is missing, the route returns HTTP 400 with a clear validation error.

## Example JSON API Usage

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/secpath/mail/new"
```

Send message:

```bash
curl -s -X POST "http://localhost:5000/secpath/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'
```

Read inbox:

```bash
curl -s "http://localhost:5000/secpath/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

Destroy mailbox:

```bash
curl -s -X POST "http://localhost:5000/secpath/mail/<address>/destroy" \
  -H "Content-Type: application/json" \
  -d '{"read_key":"<read_key>"}'
```

## Testing

HTTP Mail behavior is covered in:

`tests/test_http_mail.py`

Run:

```bash
python3 -m pytest -q tests/test_http_mail.py
```
