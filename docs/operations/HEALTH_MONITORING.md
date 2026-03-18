# Health and Monitoring Endpoints

This document describes runtime observability endpoints exposed by the Flask app.

## Endpoints

### `GET /health`

Returns a lightweight health payload suitable for liveness checks.

Response fields:

- `status` - `"healthy"` when process is running
- `timestamp` - UTC timestamp
- `uptime_seconds` - process uptime
- `version` - version from the `VERSION` file
- `active_rooms` - real-time count of active in-memory chat rooms
- `checks` - coarse subsystem checks
- `runtime` - aggregate runtime stats (no message/user content)

Example:

```json
{
  "status": "healthy",
  "active_rooms": 2,
  "runtime": {
    "active_rooms": 2,
    "active_users": 3,
    "active_messages": 12,
    "pending_direct_messages": 1,
    "rate_limited_sessions": 4
  }
}
```

### `GET /health/metrics`

Returns an operational snapshot for diagnostics.

Response fields:

- `health` - same structure as `/health`
- `apm` - aggregated request/activity metrics from the in-process APM monitor
- `runtime` - aggregate chat runtime counters

This endpoint intentionally excludes sensitive values and message contents.

## Notes

- All values are in-memory and reset on process restart.
- These endpoints are intended for operators/automation, not end-user UI.
- Runtime stats expose only aggregate counts for privacy.
