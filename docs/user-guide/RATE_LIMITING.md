# Rate Limiting and Retry Behavior

This document describes how OpSecChat rate limits write-heavy chat endpoints and how clients should retry safely.

## Overview

OpSecChat applies request limits per client session using Flask-Limiter. When a limit is exceeded, the server returns:

- HTTP `429 Too Many Requests`
- A `Retry-After` response header
- A JSON body with retry metadata

## Endpoints and Limits

- `POST /chat/create`: `10 per hour; 3 per minute`
- `POST /chat/room/<room_id>/messages`: `60 per minute`
- `POST /chat/dm/send`: `20 per hour; 5 per minute`

Read endpoints (for example `GET /chat`, `GET /chat/room/<room_id>/messages`) are not subject to these write limits.

## Structured 429 Response

When throttled, clients receive a response like:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Back off and retry later.",
  "retry_after_seconds": 17,
  "endpoint": "chat_create"
}
```

The `Retry-After` header is also set and mirrors `retry_after_seconds`.

## Discovering Current Policies

Clients can query the limits endpoint:

```http
GET /chat/limits
```

Example response:

```json
{
  "chat_create": "10 per hour; 3 per minute",
  "chat_message_write": "60 per minute",
  "dm_send": "20 per hour; 5 per minute",
  "retry_hint": "On 429 responses, honor Retry-After and retry_after_seconds."
}
```

## Client Retry Guidance

1. If response status is `429`, read `Retry-After`.
2. Wait exactly that many seconds before retry.
3. Avoid immediate loops; use one retry at a time.
4. For interactive UIs, show users the countdown.

This preserves service availability while keeping chat interactions predictable.
