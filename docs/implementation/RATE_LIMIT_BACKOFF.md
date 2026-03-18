# Rate Limiting Backoff and Retry Metadata

## Summary

The simple chat write endpoints now apply **exponential backoff** on repeated rate-limit violations and return standardized retry metadata for clients.

This improves abuse resistance and gives API consumers deterministic retry guidance.

## Endpoints Covered

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

## Behavior

Rate limiting still uses per-session sliding windows, but repeated violations now increase cooldown duration.

- First violation uses the larger of:
  - remaining sliding-window time, and
  - endpoint backoff base delay.
- Repeated violations apply exponential growth (`base * 2^(n-1)`), bounded by endpoint max backoff.
- Violation counts decay after quiet periods (no violations for one or more full windows).

## 429 Response Format

When blocked, endpoints return:

```json
{
  "error": "Rate limit exceeded. ...",
  "retry_after": 12,
  "retry_strategy": "exponential_backoff"
}
```

Headers:

- `Retry-After: <seconds>`
- `X-RateLimit-Retry-After: <seconds>`

## Configuration

Backoff settings live in `simple_chat_routes.py` under `RATE_LIMITS`:

- `max_requests`
- `window_seconds`
- `backoff_base_seconds`
- `max_backoff_seconds`

## Tests

Coverage added in `tests/test_rate_limit_and_health.py`:

- Unit verification that backoff increases across repeated violations
- Integration verification that message endpoint 429 responses include JSON retry metadata and retry headers
