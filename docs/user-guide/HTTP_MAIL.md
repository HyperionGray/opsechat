# HTTP Mail Guide

HTTP Mail provides inbox-style messaging over plain HTTP with no SMTP or IMAP dependencies.
Everything is held in memory and expires automatically.

## Security Model

- Each mailbox has a public `address` (share this to receive messages).
- Each mailbox has a private `read_key` (required to read or delete messages).
- Without the `read_key`, inbox reads are denied by default.
- Messages expire after 24 hours.
- Message bodies are overwritten in memory before deletion.
- Destroyed mailboxes reject further writes, including stale in-process references.

## Quick Start

1. Open `/<path>/mail`
2. Create a mailbox and save:
   - `address` (public)
   - `read_key` (private)
3. Share the address (or send URL) with trusted senders.
4. Read inbox via address + read key.

## Web UI Notes

- JavaScript-enabled flow:
  - Create mailbox from the page.
  - Compose to a specific mailbox.
  - Read, delete messages, and destroy mailbox.
- No-JS fallback:
  - Compose form submits to `POST /<path>/mail/send` and uses the mailbox address field in the form body.

## HTTP API

All routes are scoped under a random per-session path:

- `GET /<path>/mail`  
  Main UI.
- `POST /<path>/mail/new`  
  Create mailbox. Returns `{address, read_key, send_url, inbox_url}`.
- `POST /<path>/mail/send`  
  Non-JS fallback send endpoint. Expects mailbox address in body (`_address_override` or `address`).
- `POST /<path>/mail/<address>/send`  
  Send to mailbox by URL address.
- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox (requires read key).
- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message (requires read key in body).
- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and scrub all messages (requires read key in body).

## Limits

- Max message body length: `2000` characters.
- Max sender length: `64` characters.
- Max subject length: `200` characters.

All content is plain text and sanitized before storage.
