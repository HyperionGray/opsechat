# HTTP Mail Guide

## Overview

HTTP Mail is the email-over-HTTP mode in OpSecChat. It avoids SMTP/IMAP and keeps mailbox data in memory.

Core model:

- Mailbox `address`: public token that senders can use
- Mailbox `read_key`: private token required to read/delete/destroy
- Default deny: no read key means no inbox access
- Auto-expiry: messages expire after 24 hours
- Secure deletion: message content is overwritten before removal

## Routes

All routes are mounted under `/{path}/mail`.

- `GET /{path}/mail`
  - Main UI
- `POST /{path}/mail/new`
  - Create mailbox
  - Returns JSON: `address`, `read_key`, `send_url`, `inbox_url`
- `POST /{path}/mail/send`
  - Direct compose endpoint
  - Accepts form or JSON payload with `address`, `subject`, `body`, `sender`
- `POST /{path}/mail/<address>/send`
  - Send directly to known mailbox address
- `GET /{path}/mail/inbox?address=<address>&key=<read_key>`
  - Address/key lookup route (HTML form-friendly)
  - Redirects to canonical inbox route
- `GET /{path}/mail/<address>/inbox?key=<read_key>`
  - Read inbox
- `POST /{path}/mail/<address>/delete/<msg_id>`
  - Delete one message (requires `read_key`)
- `POST /{path}/mail/<address>/destroy`
  - Destroy mailbox and all messages (requires `read_key`)

## Security behavior

- Input sanitization strips dangerous characters from user-controlled text fields.
- Destroyed mailboxes now reject late/stale writes from old references.
- UI assets are loaded from static files (`static/css/http_mail.css`, `static/js/http_mail.js`) to align with strict CSP (`script-src 'self'`, `style-src 'self'`).

## JSON examples

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Send message (direct compose route):

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "address": "PUBLIC_MAILBOX_ADDRESS",
    "subject": "test",
    "body": "hello",
    "sender": "alice"
  }'
```

Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/PUBLIC_MAILBOX_ADDRESS/inbox?key=PRIVATE_READ_KEY" \
  -H "Accept: application/json"
```
