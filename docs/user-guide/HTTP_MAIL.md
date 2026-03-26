# HTTP Mail User Guide

## Overview

HTTP Mail provides lightweight mailbox messaging over regular HTTP with no SMTP or IMAP dependency.
Each mailbox has:

- A public `address` (safe to share with senders)
- A private `read_key` (required to read or delete messages)

Messages are stored in memory only and automatically expire after 24 hours.

## Security Model

- Default deny for reads: wrong or missing `read_key` returns access denied.
- Mailbox addresses are random tokens.
- Read keys are high-entropy random tokens.
- Message content is overwritten in memory before deletion.
- Destroyed mailboxes reject new writes.

## UI Access

Open:

`/{path}/mail`

The page supports both JavaScript and non-JavaScript usage.

## No-JavaScript Workflow

The feature now supports a complete no-JS path:

1. Create mailbox (JavaScript-assisted creation button)
2. Send message through form POST fallback route
3. Open inbox through form GET fallback route
4. Delete messages and destroy mailbox via standard forms

### Fallback Routes

- `POST /{path}/mail/send`
  - Expects form fields: `_address_override`, `subject`, `body`, `sender`
- `GET /{path}/mail/inbox`
  - Expects query params: `_read_address`, `_read_key`
  - Redirects to canonical inbox URL on success

These routes enable progressive enhancement: users without JS can still send and read mail.

## JSON/API Usage

### Create mailbox

`POST /{path}/mail/new`

Response:

```json
{
  "success": true,
  "address": "publicAddress",
  "read_key": "privateReadKey",
  "send_url": "/{path}/mail/{address}/send",
  "inbox_url": "/{path}/mail/{address}/inbox"
}
```

### Send message

`POST /{path}/mail/{address}/send`

JSON body:

```json
{
  "subject": "hello",
  "body": "message body",
  "sender": "anonymous"
}
```

### Read inbox

`GET /{path}/mail/{address}/inbox?key={read_key}`

### Delete message

`POST /{path}/mail/{address}/delete/{msg_id}`

### Destroy mailbox

`POST /{path}/mail/{address}/destroy`

## Error Behavior

- `404` mailbox not found
- `403` invalid read key
- `400` missing required message body or missing fallback parameters
- `410` mailbox no longer available during write races (destroyed lifecycle)

## Notes

- This is not a replacement for full email protocols.
- Designed for ephemeral, in-memory, address/key-based messaging.
