# HTTP Mail Guide

HTTP Mail provides email-style messaging without SMTP/IMAP dependencies.
It is fully in-memory, mailbox-based, and default-deny for reads.

## Core Model

- **Mailbox address**: short public token you can share
- **Read key**: private secret required to read/delete/destroy
- **Send**: unauthenticated (anyone with address can post)
- **Read/Delete/Destroy**: requires read key
- **Expiry**: messages auto-expire after 24 hours

## Routes

All routes are namespaced under `/{path}/mail`.

- `GET /{path}/mail` – UI page
- `POST /{path}/mail/new` – create mailbox
- `POST /{path}/mail/<address>/send` – send directly to known address
- `POST /{path}/mail/send` – non-JS form fallback (`_address_override` in form body)
- `GET /{path}/mail/<address>/inbox?key=<read_key>` – read inbox
- `POST /{path}/mail/<address>/delete/<msg_id>` – delete message
- `POST /{path}/mail/<address>/destroy` – destroy mailbox

## Inbox Query Controls

`GET /{path}/mail/<address>/inbox` supports:

- `key` (required) – read key
- `limit` (optional, default `50`, range `1-200`)
- `offset` (optional, default `0`)
- `sender` (optional, exact sender-handle match, case-insensitive)

JSON responses include metadata:

- `total_messages`
- `returned_messages`
- `limit`
- `offset`
- `sender_filter`

## Security Notes

- Read access uses constant-time key comparison.
- Destroyed mailboxes reject stale writer references in concurrent scenarios.
- Message content is overwritten before deletion where applicable.
- Input fields are sanitized before storage/rendering.
