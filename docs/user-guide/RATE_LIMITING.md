# Rate Limiting Response Contract

OpSecChat enforces request throttling on write-heavy endpoints to reduce abuse.

When a client exceeds a limit, the server responds with:

- HTTP status: `429 Too Many Requests`
- Header: `Retry-After: <seconds>`
- JSON body:

```json
{
  "error": "Rate limit exceeded. Please retry with backoff.",
  "code": "rate_limit_exceeded",
  "retry_after_seconds": 42,
  "path": "/chat/create"
}
```

Some endpoint-specific handlers may return a more specific `error` string, but
`code` and `retry_after_seconds` remain stable for automation clients.

## Client recommendation

1. Treat `429` as retriable.
2. Respect `Retry-After` (seconds).
3. Apply exponential backoff for repeated throttles.

## Scope

This applies to API-style endpoints in the chat and messaging flows, including:

- `/chat/create`
- `/chat/room/<room_id>/messages` (POST)
- `/chat/dm/send`
