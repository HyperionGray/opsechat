# HTTP Mail Guide

Date: 2026-03-23  
Audience: Operators and developers

## Overview

HTTP Mail is a lightweight mailbox system that runs entirely over HTTP, with no SMTP or IMAP dependency.

Core model:

- Public mailbox `address` (shareable)
- Private `read_key` (secret; required for reads/deletes/destroy)
- In-memory message storage only
- Automatic message expiry after 24 hours

## Security Model

- Default deny reads: inbox access requires the exact `read_key`.
- Mailbox deletion scrubs message memory before clearing.
- Destroyed mailboxes reject later writes, including stale object references in concurrent code paths.

## API Endpoints

All endpoints are under:

`/<path>/mail`

- `GET  /<path>/mail`  
  Render HTTP Mail UI.

- `POST /<path>/mail/new`  
  Create a mailbox. Returns JSON with:
  - `address`
  - `read_key`
  - `send_url`
  - `inbox_url`

- `POST /<path>/mail/<address>/send`  
  Send message to known mailbox address.

- `POST /<path>/mail/send`  
  Form-friendly send endpoint where address is provided in request body
  (`_address_override` or `address`).

- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox.

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message (requires `read_key` in form or JSON body).

- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and all messages (requires `read_key`).

## Inbox Query Options

`GET /<path>/mail/<address>/inbox` supports optional query parameters:

- `limit` (1-500): max number of messages returned
- `order`: `asc` or `desc`
  - `desc` (default) returns newest first
  - `asc` returns oldest first

JSON inbox responses include:

- `messages`
- `returned` (count in this response)
- `order`
- `limit` (null when omitted)

## Example Usage

Create mailbox:

```bash
curl -s -X POST "http://127.0.0.1:5000/<path>/mail/new"
```

Send message:

```bash
curl -s -X POST "http://127.0.0.1:5000/<path>/mail/<address>/send" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hi","body":"hello","sender":"alice"}'
```

Read newest two:

```bash
curl -s "http://127.0.0.1:5000/<path>/mail/<address>/inbox?key=<read_key>&limit=2"
```

Read oldest first:

```bash
curl -s "http://127.0.0.1:5000/<path>/mail/<address>/inbox?key=<read_key>&order=asc"
```
