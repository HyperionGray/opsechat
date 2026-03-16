# Rate Limit Configuration

OpSecChat chat endpoints now support runtime rate-limit overrides via environment variables.

This lets operators tune chat throughput without editing code.

## Supported Endpoints

- `chat_create` (`POST /chat/create`)
- `chat_message` (`POST /chat/room/<room_id>/messages`)
- `dm_send` (`POST /chat/dm/send`)

## Environment Variables

Each endpoint supports three variables:

- `OPSECHAT_<ENDPOINT>_MAX_REQUESTS` (positive integer)
- `OPSECHAT_<ENDPOINT>_WINDOW_SECONDS` (positive integer)
- `OPSECHAT_<ENDPOINT>_FLASK_LIMIT` (Flask-Limiter expression string)

Endpoint names:

- `CHAT_CREATE`
- `CHAT_MESSAGE`
- `DM_SEND`

### Example

```bash
export OPSECHAT_CHAT_CREATE_MAX_REQUESTS=5
export OPSECHAT_CHAT_CREATE_WINDOW_SECONDS=60
export OPSECHAT_CHAT_CREATE_FLASK_LIMIT="20 per hour; 5 per minute"

export OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS=45
export OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS=60
export OPSECHAT_CHAT_MESSAGE_FLASK_LIMIT="45 per minute"
```

## Defaults

If no environment variables are set, defaults are:

- `chat_create`: `3 / 60s` (Flask-Limiter: `10 per hour; 3 per minute`)
- `chat_message`: `30 / 60s` (Flask-Limiter: `30 per minute`)
- `dm_send`: `5 / 60s` (Flask-Limiter: `20 per hour; 5 per minute`)

## Validation Rules

- Non-integer or non-positive values are ignored.
- Invalid values fall back to the built-in defaults.
- If `*_FLASK_LIMIT` is not provided, endpoint defaults are used.
