# HTTP Mail User Guide

## Overview

HTTP Mail provides an ephemeral mailbox system that runs entirely over HTTP.
It does not depend on SMTP or IMAP and keeps all content in memory.

Each mailbox has:
- A public `address` used by senders
- A private `read_key` required to read or delete messages

Without a valid `read_key`, inbox access is denied by default.

## Security Model

- Messages are stored in memory only
- Messages expire automatically after 24 hours
- Message content is overwritten in memory before deletion
- Mailboxes can be destroyed permanently with the mailbox read key

## Route Summary

All routes are namespaced under `/{path}/mail`.

- `GET /{path}/mail`  
  Main HTTP Mail page (create mailbox, send, read inbox)
- `POST /{path}/mail/new`  
  Create mailbox, returns JSON with `address` and `read_key`
- `POST /{path}/mail/send`  
  Send message using address from request payload/form
- `POST /{path}/mail/{address}/send`  
  Send message directly to a specific mailbox address
- `GET /{path}/mail/{address}/inbox?key={read_key}`  
  Read inbox (requires read key)
- `POST /{path}/mail/{address}/delete/{msg_id}`  
  Delete one message (requires read key)
- `POST /{path}/mail/{address}/destroy`  
  Destroy mailbox and scrub all messages (requires read key)

## API Examples

### 1) Create a mailbox

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/new"
```

Example response:

```json
{
  "success": true,
  "address": "aBcDeFgHiJkL",
  "read_key": "32_char_private_key_here",
  "send_url": "/<path>/mail/aBcDeFgHiJkL/send",
  "inbox_url": "/<path>/mail/aBcDeFgHiJkL/inbox"
}
```

### 2) Send via generic endpoint

```bash
curl -s -X POST "http://localhost:5000/<path>/mail/send" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "aBcDeFgHiJkL",
    "subject": "Test",
    "body": "Hello over HTTP Mail",
    "sender": "alice"
  }'
```

### 3) Read inbox

```bash
curl -s "http://localhost:5000/<path>/mail/aBcDeFgHiJkL/inbox?key=32_char_private_key_here" \
  -H "Accept: application/json"
```

## No-JavaScript Compatibility

The compose form now posts to `POST /{path}/mail/send` and includes the
recipient address as form data. This keeps message sending functional even when
JavaScript is disabled.
