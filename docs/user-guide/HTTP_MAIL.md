# HTTP Mail Guide

## Overview

HTTP Mail provides temporary, in-memory mailboxes without SMTP/IMAP. Each mailbox has:

- A public `address` (safe to share with senders)
- A private `read_key` (required to read/delete/destroy)

Default behavior is deny-by-default: no `read_key`, no inbox access.

## Core Endpoints

Base path: `/<path>/mail`

- `POST /<path>/mail/new`
  - Creates a mailbox.
  - Returns `address`, `read_key`, `send_url`, and `inbox_url`.
- `POST /<path>/mail/<address>/send`
  - Sends a message to a mailbox.
  - Accepts JSON or form data with `subject`, `body`, `sender`.
- `POST /<path>/mail/send`
  - Form-compatibility endpoint.
  - Same behavior as `/mail/<address>/send`, but reads destination from `_address_override` (form) or `address` (JSON).
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Reads inbox contents (JSON or HTML).
- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Deletes one message (requires `read_key` in body).
- `POST /<path>/mail/<address>/destroy`
  - Destroys a mailbox and scrubs in-memory message content.

## Inbox Query Options

`GET /<path>/mail/<address>/inbox` supports optional query filters:

- `sender=<value>`
  - Exact sender match (case-insensitive).
- `subject_contains=<text>`
  - Subject substring match (case-insensitive).
- `newest=1` (or `true`, `yes`, `on`)
  - Sort newest first.
- `limit=<n>`
  - Max messages returned (`0..200`).
- `offset=<n>`
  - Skip first `n` messages (`0..10000`).

JSON responses now include:

- `count`: number of messages in this page
- `total`: total matching messages before pagination
- `filters`: effective filters used by the request

## Security and Lifecycle

- Messages are kept in memory only.
- Messages expire after 24 hours.
- Message content is overwritten before deletion.
- Destroyed mailboxes reject future writes and are removed from global lookup.

## Example

```bash
# 1) Create mailbox
curl -s -X POST http://localhost:5000/abc123/mail/new

# 2) Send a message
curl -s -X POST http://localhost:5000/abc123/mail/MAILBOX_ADDRESS/send \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","body":"test message","sender":"alice"}'

# 3) Read with filters
curl -s "http://localhost:5000/abc123/mail/MAILBOX_ADDRESS/inbox?key=READ_KEY&sender=alice&subject_contains=hello&newest=1&limit=10&offset=0" \
  -H "Accept: application/json"
```
