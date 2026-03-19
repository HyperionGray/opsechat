# Rate Limit Backoff

## Summary

Chat write endpoints now use progressive backoff when a client repeatedly exceeds limits.
In addition to the existing per-endpoint request windows, blocked clients receive a
standardized `429` response body and `Retry-After` header.

## Affected Endpoints

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

## Behavior

Each endpoint is checked against a sliding window limit (`max_requests` within
`window_seconds`). When exceeded:

1. Request is rejected with `429 Too Many Requests`.
2. Violation count for `(session_id, endpoint)` is incremented.
3. Retry delay is calculated as:
   - Remaining time in current window, and
   - Exponential backoff (`base * 2^(violations-1)`) capped at `backoff_max_seconds`.
4. Effective `retry_after_seconds` is the maximum of those two values.

If the client stays quiet past `violation_reset_seconds`, backoff state is reset.

## API Contract for 429

Example response:

```json
{
  "error": "Rate limit exceeded. Try again in 14 seconds.",
  "retry_after_seconds": 14,
  "retry_strategy": "exponential_backoff"
}
```

Response headers include:

- `Retry-After: 14`

## Operational Notes

- Backoff state is in-memory and automatically cleaned up by the existing background cleanup loop.
- Limits are per session identifier, with existing Flask-Limiter protection still active.
