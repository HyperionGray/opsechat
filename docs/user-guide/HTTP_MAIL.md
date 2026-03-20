# HTTP Mail User Guide

## Overview

HTTP Mail is an ephemeral mailbox system that works entirely over HTTP.
It does not use SMTP or IMAP.

Each mailbox has:
- A public `address` (safe to share with senders)
- A private `read_key` (required to read and manage messages)

Default deny behavior is enforced:
- Anyone with the address can send
- Only holders of the read key can read/delete/destroy

Messages are kept in memory and expire automatically after 24 hours.

## Quick Start

1. Open `/<path>/mail`
2. Click `Create Mailbox`
3. Save both values immediately:
   - mailbox address
   - read key
4. Share the address (or send URL) with senders
5. Read inbox with address + read key

## Routes

All routes are under `/<path>/mail`.

- `GET /<path>/mail`
  - Main HTTP Mail UI
- `POST /<path>/mail/new`
  - Creates a mailbox and returns `address` + `read_key`
- `POST /<path>/mail/send`
  - Generic compose endpoint; accepts mailbox address in payload
  - Form field: `_address_override`
  - JSON field: `address`
- `POST /<path>/mail/<address>/send`
  - Direct send endpoint when mailbox address is in the URL
- `GET /<path>/mail/<address>/inbox?key=<read_key>`
  - Read messages (read key required)
- `POST /<path>/mail/<address>/delete/<msg_id>`
  - Delete one message (read key required)
- `POST /<path>/mail/<address>/destroy`
  - Destroy mailbox and scrub messages from memory (read key required)

## Security Notes

- Message payloads are sanitized to plain text
- Inbox reads require exact read key match
- Deleted messages are overwritten in memory before removal
- Destroyed mailboxes reject future writes, including stale references

## API Example

Create mailbox:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Send message via generic endpoint:

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "MAILBOX_ADDRESS",
    "subject": "hello",
    "body": "test message",
    "sender": "anon"
  }'
```

Read inbox:

```bash
curl -s "http://localhost:5000/<path>/mail/MAILBOX_ADDRESS/inbox?key=READ_KEY" \
  -H "Accept: application/json"
```
