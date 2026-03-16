# Health Runtime Metrics and Configurable Chat Limits

## Summary

This update improves operational visibility and control for simple chat routes:

- `/health` now includes live simple-chat runtime metrics.
- In-memory simple-chat rate limits are now configurable via environment variables.

## `/health` Additions

The health payload now includes:

- `active_rooms`: number of active in-memory chat rooms
- `active_dms`: number of active in-memory direct messages
- `active_rate_limit_sessions`: number of sessions currently tracked by in-memory rate limiting
- `simple_chat_rate_limits`: effective per-endpoint in-memory limits used by simple chat routes

Example:

```json
{
  "status": "healthy",
  "version": "0.8.0-alpha",
  "active_rooms": 1,
  "active_dms": 0,
  "active_rate_limit_sessions": 3,
  "simple_chat_rate_limits": {
    "chat_create": { "max_requests": 10, "window_seconds": 60 },
    "chat_message": { "max_requests": 30, "window_seconds": 60 },
    "dm_send": { "max_requests": 5, "window_seconds": 60 }
  }
}
```

## Environment Variables

You can tune simple-chat in-memory limits with:

- `OPSECHAT_CHAT_CREATE_MAX_REQUESTS` (default: `10`)
- `OPSECHAT_CHAT_CREATE_WINDOW_SECONDS` (default: `60`)
- `OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS` (default: `30`)
- `OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS` (default: `60`)
- `OPSECHAT_DM_SEND_MAX_REQUESTS` (default: `5`)
- `OPSECHAT_DM_SEND_WINDOW_SECONDS` (default: `60`)

Only positive integer values are accepted. Invalid values safely fall back to defaults.
