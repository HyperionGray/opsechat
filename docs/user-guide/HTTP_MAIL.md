# HTTP Mail Guide

## Overview

HTTP Mail provides an inbox model that does not depend on SMTP or IMAP.
It is intended for short-lived, in-memory message exchange with a
default-deny read model.

Core properties:

- Mailbox address is public (safe to share with senders)
- Read key is private (required to read and delete messages)
- Anyone with the address can send
- Only the read key holder can read/delete/destroy
- Messages expire automatically after 24 hours
- Data is in memory only; deleted messages are overwritten before removal

## Endpoints

All endpoints are namespaced under:

`/<path>/mail`

### Create mailbox

- Method: `POST`
- Endpoint: `/<path>/mail/new`
- Response includes:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

### Send message (address in URL)

- Method: `POST`
- Endpoint: `/<path>/mail/<address>/send`
- Accepts JSON or form payload
- Required field: `body`
- Optional fields: `subject`, `sender`

### Send message (no-JavaScript form flow)

- Method: `POST`
- Endpoint: `/<path>/mail/send`
- Required form fields:
  - `_address_override` (target mailbox address)
  - `body`
- Optional form fields:
  - `subject`
  - `sender`

This endpoint exists so compose works in strict no-JavaScript mode.

### Read inbox

- Method: `GET`
- Endpoint: `/<path>/mail/<address>/inbox?key=<read_key>`
- Invalid/missing key returns access denied

### Delete message

- Method: `POST`
- Endpoint: `/<path>/mail/<address>/delete/<msg_id>`
- Requires `read_key` in body

### Destroy mailbox

- Method: `POST`
- Endpoint: `/<path>/mail/<address>/destroy`
- Requires `read_key` in body
- Overwrites and clears all in-memory message content

## Security and lifecycle behavior

### Destroyed mailbox write protection

Mailbox destruction now sets an internal `destroyed` flag under mailbox lock.
Concurrent send attempts are rejected safely if they race with destruction.

Expected behavior:

- Mailbox not found: `404`
- Invalid key for protected action: `403`
- Mailbox became unavailable during write race: `410`

### Input handling

- Subject, body, and sender are sanitized
- Body length is capped by `MAX_MAIL_MESSAGE_LENGTH`
- Empty body is rejected

## Testing

Primary tests:

- `tests/test_http_mail.py`

Coverage includes:

- mailbox lifecycle
- default-deny read access
- no-JS send endpoint behavior
- destroyed mailbox write rejection
