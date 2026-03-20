# HTTP Mail Quick Start

HTTP Mail is a lightweight mailbox system that works entirely over HTTP.
It does not depend on SMTP/IMAP and stores messages in memory only.

## What You Get

When you create a mailbox, you receive:

- `address` (public): share this so others can send messages
- `read_key` (private): required to read or delete messages

Messages expire automatically after 24 hours.

## Web UI Flow

1. Open `/<path>/mail`
2. Click **Create New Mailbox**
3. Save both the mailbox address and read key
4. Use **Send a Message** to send to an address
5. Use **Read My Inbox** with address + read key

The compose form now supports a no-JavaScript fallback endpoint (`POST /<path>/mail/send`), so sending still works even if client-side form-action rewrites are unavailable.

## API Endpoints

Base path: `/<path>/mail`

- `POST /new`  
  Create mailbox. Returns JSON with `address` and `read_key`.

- `POST /<address>/send`  
  Send message directly to a known mailbox address.

- `POST /send`  
  Form-friendly fallback send route using `_address_override` (or `address`) in the request body.

- `GET /<address>/inbox?key=<read_key>`  
  Read inbox (default deny; wrong key returns 403).

- `POST /<address>/delete/<msg_id>`  
  Delete one message (requires `read_key`).

- `POST /<address>/destroy`  
  Destroy mailbox and scrub all messages (requires `read_key`).

## Security Model

- Default deny on reads: correct `read_key` is required
- Message fields are sanitized before storage
- Message/mailbox deletion overwrites in-memory content before clearing
- Destroyed mailboxes reject subsequent writes

## Notes

- Storage is in-memory and process-local, not durable
- This is useful for short-lived operational inboxes, not long-term archival
