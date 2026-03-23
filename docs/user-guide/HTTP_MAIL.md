# HTTP Mail Guide

## Overview

HTTP Mail is an in-memory mailbox transport for OpSecChat that does not require SMTP or IMAP.
Each mailbox has:

- Public `address` (safe to share with senders)
- Private `read_key` (required to read/delete/destroy)

Messages expire automatically after 24 hours and are overwritten in memory before removal.

## Endpoints

All routes are namespaced under `/<path>/mail`.

- `GET /<path>/mail`  
  Open the HTTP Mail UI.

- `POST /<path>/mail/new`  
  Create a mailbox and return:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

- `POST /<path>/mail/send`  
  Dynamic send endpoint (works without JavaScript route rewriting).
  - JSON body: `{"address":"...", "subject":"...", "body":"...", "sender":"..."}`
  - Form body: `_address_override`, `subject`, `body`, `sender`

- `POST /<path>/mail/<address>/send`  
  Address-specific send endpoint.

- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read mailbox contents.

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message (requires `read_key`).

- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and wipe in-memory contents (requires `read_key`).

## Example (JSON API)

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Send message using dynamic endpoint:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -d '{"address":"<address>","subject":"hello","body":"test message","sender":"anon"}'
```

Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/<address>/inbox?key=<read_key>" \
  -H "Accept: application/json"
```

## Security Notes

- Default deny: wrong key returns no messages.
- Destroyed mailboxes reject stale writes.
- Message text is sanitized for the web UI.
- Storage is process-memory only and not persisted to disk.
