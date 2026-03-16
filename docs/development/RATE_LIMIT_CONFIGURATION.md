# Simple Chat Rate Limit Configuration

Simple chat endpoints use an in-memory sliding-window limiter in `simple_chat_routes.py`.

## Environment Variables

Set these before starting the server:

- `OPSECHAT_CHAT_CREATE_MAX_REQUESTS` (default: `10`)
- `OPSECHAT_CHAT_CREATE_WINDOW_SECONDS` (default: `60`)
- `OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS` (default: `30`)
- `OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS` (default: `60`)
- `OPSECHAT_DM_SEND_MAX_REQUESTS` (default: `5`)
- `OPSECHAT_DM_SEND_WINDOW_SECONDS` (default: `60`)

Invalid values (non-integer or `<= 0`) are ignored and fall back to defaults.

## 429 Response Contract

When a request is blocked by the in-memory limiter, the API returns:

- HTTP status `429`
- `Retry-After` header
- `X-RateLimit-Limit` header (max requests in the active window)
- JSON body:

```json
{
  "error": "Rate limit exceeded",
  "endpoint": "dm_send",
  "retry_after_seconds": 12,
  "limit": {
    "max_requests": 5,
    "window_seconds": 60,
    "remaining": 0
  }
}
```

## Operator Notes

- Existing Flask-Limiter route decorators are still active as an additional protection layer.
- The environment variables above control the in-memory per-session limiter used by simple chat routes.
