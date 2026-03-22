# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over HTTP only (no SMTP/IMAP).

## Overview

- Create a mailbox to receive a public **address** and private **read key**.
- Share only the address with senders.
- Keep the read key secret; inbox reads are denied without it.
- Data is in-memory only and messages auto-expire after 24 hours.

## UI Route

- `GET /<path>/mail`

This page supports:

1. Creating mailboxes
2. Sending messages
3. Reading inbox messages
4. Deleting messages
5. Destroying an entire mailbox

## API Endpoints

- `POST /<path>/mail/new`
  - Creates mailbox and returns `{ address, read_key, send_url, inbox_url }`.

- `POST /<path>/mail/send`
  - Fallback send endpoint (works without JavaScript route rewriting).
  - Accepts `address` (JSON) or `_address_override` (form), plus `subject`, `body`, `sender`.

- `POST /<path>/mail/<address>/send`
  - Route-address send endpoint.
  - Accepts JSON or form payloads.

- `GET /<path>/mail/<address>/inbox?key=<read_key>[&q=...][&sender=...][&limit=...]`
  - Reads inbox with optional filters:
    - `q`: case-insensitive search over subject/body
    - `sender`: exact sender match (case-insensitive)
    - `limit`: maximum number of returned messages (1-200)

- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Deletes a single message (requires `read_key` in JSON or form).

- `POST /<path>/mail/<address>/destroy`
  - Destroys mailbox and scrubs in-memory message content (requires `read_key`).

## Security Notes

- Default-deny inbox reads with constant-time key comparison.
- Input sanitization is applied to subject, sender, and body.
- Template JS/CSS is served from static files to comply with strict CSP (`script-src 'self'`, `style-src 'self'`).
