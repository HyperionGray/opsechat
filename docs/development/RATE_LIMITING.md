# Rate Limiting and Backoff

Last updated: 2026-03-16

## Overview

Simple chat write endpoints use a shared in-memory sliding-window limiter in `simple_chat_routes.py`.

Protected endpoints:

- `POST /chat/create` (`chat_create`)
- `POST /chat/room/<room_id>/messages` (`chat_message`)
- `POST /chat/dm/send` (`dm_send`)

Read endpoints are not throttled.

## Configuration

Defaults:

- `chat_create`: `3/60`
- `chat_message`: `30/60`
- `dm_send`: `5/60`

Override with environment variables:

- `OPSECHAT_RATE_LIMIT_CHAT_CREATE`
- `OPSECHAT_RATE_LIMIT_CHAT_MESSAGE`
- `OPSECHAT_RATE_LIMIT_DM_SEND`

Accepted formats:

- `<max>/<window_seconds>` (example: `50/120`)
- `<max>` (uses default window)

Invalid values are ignored and defaults are kept.

## 429 Response Contract

When a limit is exceeded, the API returns HTTP `429` with structured JSON:

```json
{
  "error": "Rate limit exceeded for chat_message. Retry in 12 seconds.",
  "error_code": "rate_limit_exceeded",
  "endpoint": "chat_message",
  "retry_after": 12,
  "limit": {
    "max_requests": 30,
    "window_seconds": 60
  }
}
```

Response headers include:

- `Retry-After`
- `X-RateLimit-Endpoint`
- `X-RateLimit-Limit`
- `X-RateLimit-Window`

## Client Backoff and Retry

`templates/simple_chat_room.html` now:

1. Detects `429` responses.
2. Uses `retry_after` (or `Retry-After`) to start a countdown.
3. Disables the send button during the backoff window.
4. Automatically retries the blocked message once the backoff expires.

This avoids repeated hammering while giving users predictable feedback.
