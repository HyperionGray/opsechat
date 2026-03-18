# Rate Limiting and Backoff

This guide explains how write-endpoint throttling works in OpSecChat and how to tune it for your deployment.

## What is protected

The simple chat API applies per-session rate limits to write actions:

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

If a client exceeds a limit, the API returns `429 Too Many Requests` with:

- `Retry-After`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## Exponential backoff

Repeated abuse triggers exponential backoff, which increases lockout duration after each violation.

Default behavior:

- Base backoff: 5 seconds
- Growth: doubles per repeated violation
- Maximum backoff: 300 seconds
- Violation history reset: 900 seconds of quiet time

This backoff is applied in addition to the normal sliding-window limit.

## Environment configuration

Use environment variables to tune thresholds without code changes:

### Endpoint limits

- `OPSECHAT_CHAT_CREATE_MAX_REQUESTS`
- `OPSECHAT_CHAT_CREATE_WINDOW_SECONDS`
- `OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS`
- `OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS`
- `OPSECHAT_DM_SEND_MAX_REQUESTS`
- `OPSECHAT_DM_SEND_WINDOW_SECONDS`

### Backoff controls

- `OPSECHAT_RATE_BACKOFF_BASE_SECONDS`
- `OPSECHAT_RATE_BACKOFF_MAX_SECONDS`
- `OPSECHAT_RATE_BACKOFF_RESET_AFTER_SECONDS`

Invalid values safely fall back to defaults.

## Example configuration

```bash
export OPSECHAT_CHAT_CREATE_MAX_REQUESTS=8
export OPSECHAT_CHAT_CREATE_WINDOW_SECONDS=60
export OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS=20
export OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS=60
export OPSECHAT_DM_SEND_MAX_REQUESTS=4
export OPSECHAT_DM_SEND_WINDOW_SECONDS=60

export OPSECHAT_RATE_BACKOFF_BASE_SECONDS=10
export OPSECHAT_RATE_BACKOFF_MAX_SECONDS=240
export OPSECHAT_RATE_BACKOFF_RESET_AFTER_SECONDS=1200
```

## Operational guidance

- Start with conservative defaults for public deployments.
- Monitor `429` rates and adjust thresholds gradually.
- Keep stricter limits on room creation and DMs than on message posting.
