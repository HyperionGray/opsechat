# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over HTTP without SMTP/IMAP.

It is designed for low-friction, in-memory message exchange:

- A mailbox has a public `address` (share with senders)
- A mailbox has a private `read_key` (required to read/delete)
- Messages expire automatically after 24 hours
- Message content is overwritten in memory before deletion

## Quick Start

1. Open `/{path}/mail`
2. Create a mailbox
3. Save both values shown:
   - `address`
   - `read_key`
4. Share only the `address` with senders
5. Open inbox with `address + read_key`

## API Endpoints

All routes are under:

`/{path}/mail`

- `GET /{path}/mail`
  - Render HTTP Mail UI

- `POST /{path}/mail/new`
  - Create mailbox
  - Returns JSON: `address`, `read_key`, `send_url`, `inbox_url`

- `POST /{path}/mail/send`
  - No-JS/send-by-form endpoint
  - Recipient mailbox address supplied in payload (`_address_override` or `address`)

- `POST /{path}/mail/{address}/send`
  - Send directly to mailbox address in path

- `GET /{path}/mail/{address}/inbox?key={read_key}`
  - Read inbox (default deny without valid key)

- `POST /{path}/mail/{address}/delete/{msg_id}`
  - Delete one message (requires `read_key`)

- `POST /{path}/mail/{address}/destroy`
  - Destroy mailbox and scrub all messages (requires `read_key`)

## Security Notes

- Read access is key-gated; invalid keys return deny responses
- Destroyed mailboxes reject future writes, including stale references
- Message fields are sanitized and length-limited
- Storage is in-memory only (no mailbox persistence on disk)
