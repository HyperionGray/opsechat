# Chat Operational Stats Endpoint

This document describes the operational metrics endpoint exposed by OpSecChat:

- `GET /chat/stats`

This endpoint is intended for lightweight monitoring and dashboards. It only reports aggregate operational state and does not expose message contents.

## Query Parameters

- `include_rooms` (optional, default: `false`)
  - When `true`, include per-room summaries in `room_summaries`.
- `room_limit` (optional, default: `25`)
  - Maximum number of entries in `room_summaries`.
  - Clamped to the range `0..100`.

Examples:

```bash
curl http://localhost:5000/chat/stats
curl "http://localhost:5000/chat/stats?include_rooms=true&room_limit=10"
```

## Response Fields

Top-level fields:

- `active_rooms`: Number of active in-memory chat rooms
- `total_messages`: Total messages currently retained across rooms
- `active_users`: Sum of active users across rooms
- `pending_dms`: Number of pending direct messages
- `unread_dms`: Number of pending direct messages not yet read
- `generated_at`: UTC ISO-8601 timestamp when the payload was generated
- `uptime_seconds`: Service uptime in seconds
- `rate_limit`: Snapshot of in-memory rate limiter footprint
  - `active_sessions`
  - `tracked_endpoints`
  - `active_entries`
- `config`: Current runtime configuration values
  - `message_expiry_seconds`
  - `dm_expiry_seconds`
  - `room_inactive_seconds`
  - `rate_limits`

Optional fields (only when `include_rooms=true`):

- `room_summaries`: Array of room-level aggregates sorted by `message_count` (desc)
  - `room_id`
  - `message_count`
  - `active_users`
  - `created_age_seconds`
  - `oldest_message_age_seconds` (or `null` if no messages)
  - `newest_message_age_seconds` (or `null` if no messages)
- `room_summaries_truncated`: `true` when rooms exceed `room_limit`

## Notes

- This endpoint is read-only and safe for periodic polling.
- Values are calculated from in-memory runtime state and reset on process restart.
