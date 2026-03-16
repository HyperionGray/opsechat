# Rate Limit Configuration

OpSecChat supports environment-driven rate limit tuning for simple chat endpoints.
This allows operators to tighten or relax limits without editing Python code.

## What is configurable

Two limiter layers can be configured:

1. In-memory endpoint checks in `simple_chat_routes.py`
2. Flask-Limiter decorator strings (request throttling at route level)

Defaults are safe for local and CI use.

## Environment variables

### In-memory endpoint limits

Each endpoint supports:

- `*_MAX_REQUESTS`
- `*_WINDOW_SECONDS`

Variables:

- `OPSECHAT_LIMIT_CHAT_CREATE_MAX_REQUESTS`
- `OPSECHAT_LIMIT_CHAT_CREATE_WINDOW_SECONDS`
- `OPSECHAT_LIMIT_CHAT_MESSAGE_MAX_REQUESTS`
- `OPSECHAT_LIMIT_CHAT_MESSAGE_WINDOW_SECONDS`
- `OPSECHAT_LIMIT_DM_SEND_MAX_REQUESTS`
- `OPSECHAT_LIMIT_DM_SEND_WINDOW_SECONDS`

### Flask-Limiter decorator strings

- `OPSECHAT_LIMIT_CHAT_CREATE_DECORATOR`
- `OPSECHAT_LIMIT_CHAT_MESSAGE_DECORATOR`
- `OPSECHAT_LIMIT_DM_SEND_DECORATOR`

Examples: `1 per minute`, `30 per minute`, `10 per hour; 3 per minute`

## Defaults

In-memory defaults:

- `chat_create`: `10 requests / 60 seconds`
- `chat_message`: `30 requests / 60 seconds`
- `dm_send`: `5 requests / 60 seconds`

Decorator defaults:

- `chat_create`: `10 per hour; 3 per minute`
- `chat_message`: `60 per minute`
- `dm_send`: `20 per hour; 5 per minute`

## Example

```bash
export OPSECHAT_LIMIT_CHAT_MESSAGE_MAX_REQUESTS=15
export OPSECHAT_LIMIT_CHAT_MESSAGE_WINDOW_SECONDS=60
export OPSECHAT_LIMIT_CHAT_CREATE_DECORATOR="2 per minute"
python runserver.py
```

## Validation behavior

- Non-integer or non-positive numeric values fall back to defaults.
- Empty decorator strings are ignored and default strings are used.
