# Rate Limiting and Backoff Behavior

This document explains how OpSecChat throttles high-frequency requests and how clients should recover from `429 Too Many Requests` responses.

## What is rate limited

Write-heavy chat endpoints are throttled to reduce abuse and spam:

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

Read endpoints (for example `GET /` and message fetch endpoints) are not throttled in normal operation.

## 429 response contract

When a limit is exceeded, the server returns:

- HTTP status: `429`
- Header: `Retry-After: <seconds>`
- JSON body:

```json
{
  "error": "Rate limit exceeded. Please retry later.",
  "error_code": "rate_limit_exceeded",
  "retry_after_seconds": 12
}
```

Some endpoint-level limits also include:

- `endpoint`: which limiter scope was exceeded (for example `chat_message`)

## Client behavior recommendations

When handling `429`:

1. Read `retry_after_seconds` (or `Retry-After` header).
2. Wait at least that long before retrying.
3. Use exponential backoff for repeated `429`s.
4. Avoid hot-loop retries.

## Operator notes

- Limits are session-aware to avoid unfairly grouping multiple users behind one shared IP.
- Responses include `Cache-Control: no-store` for throttling errors.
- Current thresholds are intentionally conservative and should be tuned after load testing.
