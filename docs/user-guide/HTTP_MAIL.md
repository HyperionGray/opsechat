# HTTP Mail User Guide

HTTP Mail provides mailbox-style messaging over HTTPS/HTTP without SMTP or IMAP.
It is designed for ephemeral, in-memory message handling with default-deny inbox reads.

## Security model

- A mailbox has a public **address** (share this to receive messages).
- A mailbox has a private **read key** (required to read/delete/destroy).
- Anyone with the address can send.
- Only holders of the read key can read inbox contents.
- Messages auto-expire after 24 hours.
- Data is memory-only and overwritten on delete/destroy paths.

## Endpoints

All routes are namespaced under `/<path>/mail`.

### Mailbox management

- `POST /<path>/mail/new`
  - Creates a mailbox.
  - Returns JSON with `address`, `read_key`, `send_url`, and `inbox_url`.

- `POST /<path>/mail/<address>/destroy`
  - Destroys the mailbox (requires `read_key`).
  - Overwrites and clears existing messages in memory.
  - After destroy, stale mailbox references can no longer accept writes.

### Sending

- `POST /<path>/mail/<address>/send`
  - Canonical send endpoint (JSON or form payload).

- `POST /<path>/mail/send`
  - Compose-form fallback endpoint (form only).
  - Accepts mailbox address in `_address_override`.
  - Supports non-JavaScript clients and server-rendered compose flow.

### Reading and message deletion

- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Reads inbox (JSON when `Accept: application/json`).

- `POST /<path>/mail/<address>/delete/<message_id>`
  - Deletes one message (requires `read_key`).

## Typical flow

1. Create mailbox via `POST /mail/new`.
2. Share `address` or `send_url` with senders.
3. Read with `GET /mail/<address>/inbox?key=<read_key>`.
4. Delete individual messages or destroy mailbox when done.

## Notes

- If you lose the read key, inbox access is intentionally unrecoverable.
- If mailbox address is missing in compose form requests, server returns `400`.
