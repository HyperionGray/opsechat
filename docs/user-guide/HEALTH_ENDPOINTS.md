# Health Endpoints

This guide documents the service health endpoints exposed by OpSecChat.

## Endpoints

### `GET /health`
Returns a general health payload for operators and dashboards.

Example fields:
- `status` - `healthy` or `degraded`
- `uptime_seconds`
- `version`
- `active_rooms`
- `active_users`
- `active_direct_messages`
- `rate_limited_sessions`
- `checks.cleanup_thread`

### `GET /healthz`
Alias for `/health` (Kubernetes-friendly naming).

### `GET /health/live`
Liveness probe endpoint. Indicates whether the process is up and serving HTTP.

Response:
- `status` = `alive`
- `timestamp`
- `version`

### `GET /health/ready`
Readiness probe endpoint. Indicates whether chat runtime components are ready.

Response:
- `status` = `ready` or `not_ready`
- `ready` = `true` or `false`
- `checks.cleanup_thread`
- `runtime` (active rooms/users/DMs/rate-limit session counters)

HTTP status:
- `200` when ready
- `503` when not ready

### `GET /readyz`
Alias for `/health/ready`.

## Notes

- Health endpoints do not expose message contents.
- Runtime counters are in-memory snapshots and may change quickly under load.
