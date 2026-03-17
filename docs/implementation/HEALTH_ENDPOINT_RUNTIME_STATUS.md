# Health Endpoint Runtime Status

Date: 2026-03-17

## Overview

The `/health` endpoint now reports live operational counters for the simple chat
subsystem in addition to basic process health.

This closes an unfinished gap where health checks existed but did not provide
enough runtime context for operators.

## What was added

- `active_rooms`: number of currently active chat rooms
- `active_users`: aggregate active user count across rooms
- `active_direct_messages`: current direct-message entries not yet expired
- `total_room_messages`: count of currently retained room messages
- `active_rate_limited_sessions`: sessions with active in-memory rate-limit state
- `rate_limits`: effective endpoint-level rate-limit configuration

Before returning health data, the runtime performs a lightweight cleanup pass so
expired rooms, DMs, and stale rate-limit windows do not inflate counters.

## Example response

```json
{
  "status": "healthy",
  "timestamp": "2026-03-17T03:14:52.168954",
  "uptime_seconds": 114.13,
  "version": "0.8.0-alpha",
  "active_rooms": 1,
  "active_users": 2,
  "active_direct_messages": 0,
  "total_room_messages": 4,
  "active_rate_limited_sessions": 1,
  "rate_limits": {
    "chat_create": {"max_requests": 10, "window_seconds": 60},
    "chat_message": {"max_requests": 30, "window_seconds": 60},
    "dm_send": {"max_requests": 5, "window_seconds": 60}
  },
  "checks": {
    "tor_connection": "unknown",
    "memory_usage": "ok",
    "disk_space": "ok",
    "simple_chat_state": "ok"
  }
}
```

## Validation

New integration assertions were added in `tests/test_rate_limit_and_health.py`
to verify:

1. the health endpoint includes the rate-limit configuration, and
2. room counters update after `POST /chat/create`.
