# HTTP Mail Guide

HTTP Mail is a mailbox system that works entirely over HTTP with no SMTP or IMAP dependency.
It is designed for simple, temporary inboxes with default-deny reads.

## Security model

- Every mailbox has:
  - A public `address` (safe to share with senders)
  - A private `read_key` (required to read, delete, rotate, or destroy)
- Mailboxes and messages are in-memory only.
- Messages automatically expire after 24 hours.
- Message content is overwritten in memory before deletion.
- If a mailbox is destroyed, it is marked unavailable and no new messages are accepted.

## Routes

All routes are under `/{path}/mail`.

- `GET /{path}/mail`
  - HTTP Mail UI
- `POST /{path}/mail/new`
  - Create mailbox
- `POST /{path}/mail/send`
  - Send message using form-provided mailbox address
- `POST /{path}/mail/<address>/send`
  - Send message directly to a mailbox address
- `GET /{path}/mail/<address>/inbox?key=<read_key>`
  - Read inbox (default deny without valid key)
- `POST /{path}/mail/<address>/rotate-key`
  - Rotate read key (requires current valid key)
- `POST /{path}/mail/<address>/delete/<msg_id>`
  - Delete one message (requires valid key)
- `POST /{path}/mail/<address>/destroy`
  - Destroy mailbox and scrub messages (requires valid key)

## Read-key rotation

Read-key rotation lets mailbox owners invalidate previously shared read links.

Behavior:

1. Client sends current key to `POST /mail/<address>/rotate-key`
2. Server verifies the key using constant-time comparison
3. Server generates and returns a new 32-character read key
4. Old key immediately stops working

Recommendation:

- Rotate key after accidental exposure or when access scope changes.
- Store the new key immediately; old links fail after rotation.

## UI and CSP compatibility

HTTP Mail UI uses static assets:

- `static/http_mail.css`
- `static/http_mail.js`

This keeps the page compatible with strict CSP headers:

- `script-src 'self'`
- `style-src 'self'`

No inline `<script>` or `<style>` blocks are required.
