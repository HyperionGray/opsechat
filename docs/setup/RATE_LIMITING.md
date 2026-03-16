## Rate Limiting Configuration

OpSecChat applies per-session limits to write endpoints and supports runtime
configuration through environment variables.

### Endpoints Covered

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

### Configuration Variables

All values must be positive integers, except `*_MAX_PER_HOUR` which can be `0`
to disable the hourly cap for that endpoint.

| Variable | Default | Description |
| --- | ---: | --- |
| `OPSECHAT_CHAT_CREATE_MAX_PER_MINUTE` | `3` | Room creation requests per minute |
| `OPSECHAT_CHAT_CREATE_MAX_PER_HOUR` | `10` | Room creation requests per hour |
| `OPSECHAT_CHAT_MESSAGE_MAX_PER_MINUTE` | `30` | Room message posts per minute |
| `OPSECHAT_CHAT_MESSAGE_MAX_PER_HOUR` | `0` | Room message posts per hour (`0` = disabled) |
| `OPSECHAT_DM_SEND_MAX_PER_MINUTE` | `5` | DM sends per minute |
| `OPSECHAT_DM_SEND_MAX_PER_HOUR` | `20` | DM sends per hour |

Invalid values automatically fall back to defaults.

### Runtime Inspection

The active limits can be inspected at:

- `GET /chat/rate-limits`

Example response:

```json
{
  "rate_limits": {
    "chat_create": {
      "max_per_minute": 3,
      "window_seconds": 60,
      "max_per_hour": 10
    },
    "chat_message": {
      "max_per_minute": 30,
      "window_seconds": 60,
      "max_per_hour": 0
    },
    "dm_send": {
      "max_per_minute": 5,
      "window_seconds": 60,
      "max_per_hour": 20
    }
  }
}
```
