# Rate Limit Configuration

OpSecChat rate limits can be tuned with environment variables.

These settings apply to simple chat write endpoints:

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

## Environment Variables

| Variable | Default | Description |
| --- | ---: | --- |
| `OPSECHAT_CHAT_CREATE_PER_MINUTE` | `3` | Per-session create-room requests per minute |
| `OPSECHAT_CHAT_CREATE_PER_HOUR` | `10` | Per-session create-room requests per hour (Flask-Limiter) |
| `OPSECHAT_CHAT_MESSAGE_PER_MINUTE` | `30` | Per-session chat message posts per minute |
| `OPSECHAT_DM_SEND_PER_MINUTE` | `5` | Per-session DM sends per minute |
| `OPSECHAT_DM_SEND_PER_HOUR` | `20` | Per-session DM sends per hour (Flask-Limiter) |
| `OPSECHAT_DEFAULT_LIMIT_PER_MINUTE` | `50` | Default Flask-Limiter fallback for routes without explicit limits |
| `OPSECHAT_DEFAULT_LIMIT_PER_HOUR` | `200` | Default Flask-Limiter fallback for routes without explicit limits |

## Example

```bash
export OPSECHAT_CHAT_CREATE_PER_MINUTE=5
export OPSECHAT_CHAT_CREATE_PER_HOUR=25
export OPSECHAT_CHAT_MESSAGE_PER_MINUTE=45
export OPSECHAT_DM_SEND_PER_MINUTE=8
export OPSECHAT_DM_SEND_PER_HOUR=40
python runserver.py
```

## Notes

- Invalid values (non-integers, empty values, or values less than `1`) are ignored and fall back to defaults.
- Limits are evaluated per session to avoid grouping users behind the same shared proxy.
