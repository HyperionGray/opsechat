# HTTP Mail Guide

HTTP Mail provides mailbox-style messaging over HTTP without SMTP/IMAP.

## Overview

Each mailbox has:

- `address` (public): safe to share with senders
- `read_key` (private): required to read, delete, or destroy mailbox content

Storage is in-memory only.

- Messages expire after 24 hours
- Mailboxes enforce bounded message retention
- Destroying a mailbox overwrites and clears message data

## Endpoints

Assuming your server path is `<path>`:

### Create mailbox

`POST /<path>/mail/new`

Response:

```json
{
  "success": true,
  "address": "abc123def456",
  "read_key": "long-secret-key",
  "send_url": "/<path>/mail/abc123def456/send",
  "inbox_url": "/<path>/mail/abc123def456/inbox"
}
```

### Send message (direct route)

`POST /<path>/mail/<address>/send`

Supports JSON or form fields:

- `subject` (optional)
- `body` (required)
- `sender` (optional)

### Send message (form-friendly route)

`POST /<path>/mail/send`

For non-JavaScript form flows, include:

- `_address_override` (required)
- `subject`, `body`, `sender`

### Read inbox

`GET /<path>/mail/<address>/inbox?key=<read_key>`

### Delete message

`POST /<path>/mail/<address>/delete/<msg_id>`

Body (JSON or form):

- `read_key` (required)

### Destroy mailbox

`POST /<path>/mail/<address>/destroy`

Body (JSON or form):

- `read_key` (required)

## Security Model

- Default deny: wrong or missing `read_key` returns access denied.
- Inputs are sanitized to plain text.
- Destroyed mailboxes reject future writes.
- If a mailbox disappears during send processing, API callers receive `410`.
