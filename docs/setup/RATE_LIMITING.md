# Rate Limiting Configuration

This project enforces write-path throttling to reduce abuse while keeping
legitimate chat usage responsive.

## What is Rate Limited

The following endpoints are protected:

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

Read endpoints (for example `GET /` or message polling) remain available under
normal global limits.

## Defaults

Current defaults are:

- Chat room creation: `3 per minute` and `10 per hour`
- Room messages: `30 per minute`
- Direct messages: `5 per minute` and `20 per hour`

When limits are exceeded, responses return HTTP `429` with:

- JSON body containing `error_code=rate_limited` and `retry_after`
- `Retry-After` response header

## Environment Variables

You can override defaults without code changes:

```bash
export OPSECHAT_CHAT_CREATE_LIMIT_PER_MINUTE=3
export OPSECHAT_CHAT_CREATE_LIMIT_PER_HOUR=10
export OPSECHAT_CHAT_MESSAGE_LIMIT_PER_MINUTE=30
export OPSECHAT_DM_SEND_LIMIT_PER_MINUTE=5
export OPSECHAT_DM_SEND_LIMIT_PER_HOUR=20
```

All values must be positive integers; invalid values fall back to defaults.

## Client Backoff Behavior

The web UI uses `retry_after`/`Retry-After` to implement countdown-based
backoff for:

- "Create New Chat Room" button
- Room message send button

This prevents repeated failing requests and gives users a clear retry time.
