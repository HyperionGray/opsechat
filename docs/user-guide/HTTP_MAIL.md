# HTTP Mail Guide

## Overview

HTTP Mail is a mailbox feature that works fully over HTTP with no SMTP or IMAP dependency.
It is designed for temporary, in-memory communication with a default-deny read model.

Routes are under:

- `/{path}/mail`

Core model:

- Mailbox address: public token you can share with senders
- Read key: private token required to read or manage the mailbox

Without the read key, inbox reads are denied.

## Security model

- Messages are in-memory only
- Messages auto-expire after 24 hours
- Message text fields are sanitized for dangerous characters
- Deletion overwrites message contents before removal
- Mailbox destruction overwrites stored messages and removes mailbox from storage

## JavaScript and non-JavaScript support

HTTP Mail supports both modes:

- JavaScript mode:
  - Create mailbox with fetch API
  - Read inbox with fetch API
  - Delete message and destroy mailbox from dynamic controls
- Non-JavaScript mode:
  - Create mailbox with normal form POST
  - Send messages with normal form POST to fallback route
  - Open inbox with normal form GET to fallback route
  - Delete and destroy with regular form submissions

This keeps the feature usable for strict browser policies and NoScript users.

## Endpoints

- `GET /{path}/mail`
  - Main HTTP Mail page
- `POST /{path}/mail/new`
  - Creates mailbox
  - Returns JSON for API clients, HTML for form submissions
- `POST /{path}/mail/send`
  - Non-JS send fallback
  - Uses form field `_address_override`
- `POST /{path}/mail/{address}/send`
  - Send message to mailbox address
- `GET /{path}/mail/inbox`
  - Non-JS inbox lookup fallback
  - Uses query params `_read_address` and `_read_key`
- `GET /{path}/mail/{address}/inbox?key=<read_key>`
  - Reads inbox with correct read key
- `POST /{path}/mail/{address}/delete/{msg_id}`
  - Deletes one message with read key
- `POST /{path}/mail/{address}/destroy`
  - Destroys mailbox with read key

## Usage flow

1. Open `/{path}/mail`
2. Create mailbox
3. Save address and read key
4. Share address with sender
5. Read inbox with address + read key
6. Optionally delete individual messages or destroy mailbox

## Testing

Relevant tests are in:

- `tests/test_http_mail.py`

Coverage includes:

- JSON API behavior
- Non-JS fallback routes (`/mail/send`, `/mail/inbox`)
- Access control for read key
- Message deletion and mailbox destruction
- Input validation and sanitization
