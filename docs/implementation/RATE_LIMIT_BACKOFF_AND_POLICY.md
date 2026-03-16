# Rate Limit Backoff and Policy Endpoint

## Summary

Chat write endpoints now return structured rate-limit metadata so clients can
back off predictably instead of retrying blindly.

This iteration introduced:

- Structured JSON responses for application-level chat throttling (`HTTP 429`)
- Standard `Retry-After` response header
- Backoff guidance in both headers and JSON payload
- A discoverable policy endpoint: `GET /chat/rate-limits`
- UI handling in chat templates to apply cooldowns automatically

## Endpoints Covered

Structured 429 responses are returned by:

- `POST /chat/create` (when app-level limit is exceeded)
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

Rate limit policy discovery:

- `GET /chat/rate-limits`

## 429 Response Shape

Example payload:

```json
{
  "error": "Rate limit exceeded. Maximum 30 requests per 60 seconds. Try again in 18 seconds.",
  "rate_limit": {
    "endpoint": "chat_message",
    "max_requests": 30,
    "window_seconds": 60,
    "retry_after_seconds": 18,
    "recommended_backoff_seconds": 36
  }
}
```

Headers:

- `Retry-After: <seconds>`
- `X-RateLimit-Backoff: <seconds>`
- `X-RateLimit-Limit: <max_requests>` (when known)
- `X-RateLimit-Window: <window_seconds>` (when known)

## Client Behavior

Web chat templates now:

- Parse structured 429 responses
- Display clear retry feedback to the user
- Temporarily disable send/create controls during cooldown
- Re-enable controls automatically when cooldown expires

This improves UX under contention and reduces repeated 429 bursts.

## Tests Added/Updated

- `tests/test_rate_limiter.py`
  - Added validation that `/chat/room/<id>/messages` returns structured 429 metadata
- `tests/test_rate_limit_and_health.py`
  - Added coverage for `GET /chat/rate-limits`

