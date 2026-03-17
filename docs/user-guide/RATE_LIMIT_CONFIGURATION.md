# Rate Limit Configuration

OpSecChat now supports environment-based configuration for simple chat write endpoints.

## Supported Variables

- `OPSECHAT_RATE_LIMIT_CHAT_CREATE`
- `OPSECHAT_RATE_LIMIT_CHAT_MESSAGE`
- `OPSECHAT_RATE_LIMIT_DM_SEND`

Each variable accepts Flask-Limiter style expressions, for example:

- `10 per hour; 3 per minute`
- `30 per minute`
- `100 per 10 second`

If an expression is invalid, OpSecChat safely falls back to the built-in default.

## Default Values

- `chat_create`: `10 per hour; 3 per minute`
- `chat_message`: `30 per minute`
- `dm_send`: `20 per hour; 5 per minute`

## Example

```bash
export OPSECHAT_RATE_LIMIT_CHAT_CREATE="6 per minute"
export OPSECHAT_RATE_LIMIT_CHAT_MESSAGE="20 per minute"
export OPSECHAT_RATE_LIMIT_DM_SEND="8 per 5 minute"
python runserver.py
```

## Notes

- The same expression now drives both Flask-Limiter decorators and the in-memory fallback checks.
- Multi-window expressions (such as `20 per hour; 5 per minute`) are enforced in-memory as well.
