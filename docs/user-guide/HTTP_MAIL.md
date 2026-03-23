# HTTP Mail Guide

HTTP Mail is a lightweight mailbox system that works over HTTP only (no SMTP/IMAP).
It is designed for short-lived, in-memory messaging where readers are authorized with a secret key.

## Overview

Each mailbox has:

- `address` (public): safe to share with senders
- `read_key` (private): required to read/delete/destroy mailbox content

Security model:

- Default deny for reads: inbox access fails without a valid `read_key`
- Messages expire after 24 hours
- Messages are overwritten in memory before deletion
- Mailboxes can be destroyed; destroyed mailboxes reject future writes

## Endpoints

All endpoints are under `/<path>/mail`.

- `GET /<path>/mail`  
  Open the HTTP Mail UI.

- `POST /<path>/mail/new`  
  Create mailbox; returns JSON with `address`, `read_key`, and helper URLs.

- `POST /<path>/mail/send`  
  Send message using address from payload (works without JavaScript).
  - Form field: `_address_override`
  - JSON field: `address`

- `POST /<path>/mail/<address>/send`  
  Send directly to a known mailbox address.

- `GET /<path>/mail/<address>/inbox?key=<read_key>`  
  Read inbox (requires valid key).

- `POST /<path>/mail/<address>/delete/<msg_id>`  
  Delete one message (requires `read_key`).

- `POST /<path>/mail/<address>/destroy`  
  Destroy mailbox and scrub in-memory messages (requires `read_key`).

## Quick Usage

1. Create mailbox from UI or `POST /mail/new`.
2. Share `address` with sender.
3. Sender posts to `/mail/send` (or `/mail/<address>/send`).
4. Reader opens inbox with `address + read_key`.

## Example JSON Send

```bash
curl -X POST "http://localhost:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "PUBLICADDRESS",
    "subject": "hello",
    "body": "message text",
    "sender": "anonymous"
  }'
```
