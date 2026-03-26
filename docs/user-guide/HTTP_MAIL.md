# HTTP Mail Guide

## Overview

HTTP Mail provides a lightweight mailbox system over HTTP with no SMTP/IMAP dependency.

- Mailbox address: public identifier you can share with senders
- Read key: private token required to read and manage mailbox contents
- Storage: in-memory only
- Expiration: messages auto-expire after 24 hours

Access path:

- `/{path}/mail`

## Security Model

HTTP Mail uses a default-deny read model:

- Anyone with mailbox address can send
- Only holder of read key can read/delete/destroy
- Message content is overwritten in memory before deletion
- Destroyed mailboxes reject late writes

### Destroy Safety Semantics

Mailbox destruction is implemented in two phases:

1. Remove mailbox from global storage map
2. Acquire mailbox lock, overwrite message content, clear message list, mark mailbox destroyed

If a send request races with mailbox destruction, write operations now fail safely and the API returns:

- `410 Gone` for JSON send attempts hitting a destroyed mailbox object
- `404 Not Found` when mailbox no longer resolves by address

## API Endpoints

All endpoints are under `/{path}/mail`.

- `GET /mail` - UI
- `POST /mail/new` - Create mailbox (returns address + read_key)
- `POST /mail/<address>/send` - Send message
- `GET /mail/<address>/inbox?key=<read_key>` - Read inbox
- `POST /mail/<address>/delete/<msg_id>` - Delete one message
- `POST /mail/<address>/destroy` - Destroy mailbox

## Example Flow

1. Create mailbox with `POST /{path}/mail/new`
2. Share returned `address` with sender
3. Sender posts to `/{path}/mail/<address>/send`
4. Owner reads via `/{path}/mail/<address>/inbox?key=<read_key>`
5. Owner optionally destroys mailbox via `/{path}/mail/<address>/destroy`

## Testing

HTTP Mail test suite:

```bash
python3 -m pytest -q tests/test_http_mail.py
```

