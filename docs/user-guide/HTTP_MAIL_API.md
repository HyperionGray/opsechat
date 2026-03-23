# HTTP Mail API

## Overview

The HTTP Mail API provides mailbox-style messaging over HTTP only.
It is designed for low-dependency operation: no SMTP, no IMAP, no disk persistence.

Key properties:

- In-memory mailboxes only
- Public mailbox address for senders
- Private `read_key` for inbox access
- Default deny on reads and deletes without the correct key
- Message overwrite before deletion

## Endpoints

Assume `{path}` is the configured runtime path segment.

### Create mailbox

- Method: `POST`
- Path: `/{path}/mail/new`
- Auth: none

Response (JSON):

```json
{
  "success": true,
  "address": "mailbox_token",
  "read_key": "private_read_key",
  "send_url": "/{path}/mail/{address}/send",
  "inbox_url": "/{path}/mail/{address}/inbox"
}
```

### Send message

- Method: `POST`
- Path: `/{path}/mail/{address}/send`
- Auth: none
- Content types: JSON or form

JSON body:

```json
{
  "subject": "optional subject",
  "body": "required body",
  "sender": "optional sender"
}
```

Response:

- `200` on success with `{"success": true, "msg_id": "..."}`
- `404` if mailbox does not exist
- `410` if mailbox object was destroyed and can no longer accept writes

### Read inbox

- Method: `GET`
- Path: `/{path}/mail/{address}/inbox`
- Auth: required query `?key=<read_key>`

If `Accept: application/json` is sent, the endpoint returns JSON and supports pagination:

- `limit` (optional, default `100`, range `1..500`)
- `offset` (optional, default `0`, range `0..100000`)

Example:

`GET /{path}/mail/{address}/inbox?key=...&limit=50&offset=100`

JSON response:

```json
{
  "address": "mailbox_token",
  "messages": [],
  "total": 0,
  "offset": 100,
  "limit": 50,
  "returned": 0,
  "has_more": false
}
```

Error responses:

- `403` invalid key
- `404` mailbox not found
- `400` invalid pagination parameters

### Delete one message

- Method: `POST`
- Path: `/{path}/mail/{address}/delete/{msg_id}`
- Auth: `read_key` in JSON body or form body

### Destroy mailbox

- Method: `POST`
- Path: `/{path}/mail/{address}/destroy`
- Auth: `read_key` in JSON body or form body

On successful destroy:

1. Mailbox is removed from global lookup.
2. Messages are overwritten and cleared under mailbox lock.
3. Mailbox is marked destroyed to block future writes via stale references.

## Security Notes

- Keep `read_key` secret. It is equivalent to inbox ownership.
- Treat mailbox addresses as semi-public routing identifiers.
- Use HTTPS/TLS at deployment boundaries where possible.
- Data is volatile by design and lost on process restart.
