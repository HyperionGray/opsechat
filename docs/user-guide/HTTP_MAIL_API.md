# HTTP Mail API Guide

## Overview

HTTP Mail provides mailbox-style messaging over HTTP without SMTP/IMAP.

- Senders only need a mailbox address.
- Readers must provide the mailbox read key.
- Messages are in-memory and expire automatically.

Base route:

`/{path}/mail`

## Endpoints

### Create mailbox

`POST /{path}/mail/new`

Response:

```json
{
  "success": true,
  "address": "aBcDeFgHiJkL",
  "read_key": "long-secret-read-key",
  "send_url": "/{path}/mail/{address}/send",
  "inbox_url": "/{path}/mail/{address}/inbox"
}
```

### Send message (API)

`POST /{path}/mail/{address}/send`

Body (JSON):

```json
{
  "sender": "alice",
  "subject": "hello",
  "body": "message text"
}
```

### Send message (form fallback)

`POST /{path}/mail/send`

Form fields:

- `_address_override` (required)
- `sender` (optional)
- `subject` (optional)
- `body` (required)

This route exists so non-JavaScript form submits can still deliver messages.

### Read inbox (JSON)

`GET /{path}/mail/{address}/inbox?key={read_key}`

Optional query parameters:

- `limit` (non-negative integer): max messages to return
- `offset` (non-negative integer): starting index
- `include_body` (`1/0`, `true/false`, `yes/no`): include or suppress message body text

Example:

`GET /{path}/mail/{address}/inbox?key={read_key}&limit=20&offset=40&include_body=false`

Response:

```json
{
  "address": "aBcDeFgHiJkL",
  "total_messages": 120,
  "offset": 40,
  "limit": 20,
  "returned_messages": 20,
  "messages": [
    {
      "id": "msg123",
      "subject": "status",
      "sender": "alice",
      "timestamp": "2026-03-23T00:00:00.000000"
    }
  ]
}
```

### Delete message

`POST /{path}/mail/{address}/delete/{id}`

JSON body:

```json
{"read_key": "long-secret-read-key"}
```

### Destroy mailbox

`POST /{path}/mail/{address}/destroy`

JSON body:

```json
{"read_key": "long-secret-read-key"}
```

## Errors

- `400`: invalid query/body input
- `403`: invalid read key
- `404`: mailbox not found
- `410`: mailbox exists but was destroyed during a concurrent operation
