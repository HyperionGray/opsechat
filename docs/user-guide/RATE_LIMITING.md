# Rate Limiting Configuration

OpSecChat applies request throttling on chat write endpoints to reduce abuse and accidental flooding.

There are two layers:

1. Flask-Limiter route-level limits (framework-level protection)
2. In-memory per-session limits in `simple_chat_routes.py` (app-level controls)

This document describes the in-memory configuration layer.

## Default In-Memory Limits

- `chat_create`: 10 requests per 60 seconds
- `chat_message`: 30 requests per 60 seconds
- `dm_send`: 5 requests per 60 seconds

## Environment Variables

You can override each endpoint's `max_requests` and `window_seconds` using environment variables:

- `OPSECHAT_RATE_LIMIT_CHAT_CREATE_MAX_REQUESTS`
- `OPSECHAT_RATE_LIMIT_CHAT_CREATE_WINDOW_SECONDS`
- `OPSECHAT_RATE_LIMIT_CHAT_MESSAGE_MAX_REQUESTS`
- `OPSECHAT_RATE_LIMIT_CHAT_MESSAGE_WINDOW_SECONDS`
- `OPSECHAT_RATE_LIMIT_DM_SEND_MAX_REQUESTS`
- `OPSECHAT_RATE_LIMIT_DM_SEND_WINDOW_SECONDS`

Only positive integers are accepted. Invalid values (zero, negative, non-numeric) automatically fall back to defaults.

## Runtime Visibility

The active in-memory configuration is available at:

- `GET /chat/rate-limits`

Example response:

```json
{
  "rate_limits": {
    "chat_create": { "max_requests": 10, "window_seconds": 60 },
    "chat_message": { "max_requests": 30, "window_seconds": 60 },
    "dm_send": { "max_requests": 5, "window_seconds": 60 }
  }
}
```

## Notes

- Configuration is loaded when the module is imported.
- Tests can reload configuration at runtime via `reload_rate_limits_from_env()`.
