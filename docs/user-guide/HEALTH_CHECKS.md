# Health Checks

OpSecChat exposes lightweight operational probes for container orchestrators and service monitoring.

## Endpoints

- `GET /health`
  - High-level operational status.
  - Includes runtime counters: active rooms, active direct messages, and tracked rate-limit sessions.
- `GET /health/live`
  - Liveness probe.
  - Verifies the process is running and returns version/timestamp metadata.
- `GET /health/ready`
  - Readiness probe.
  - Verifies the application is ready to serve traffic.
  - Returns HTTP `200` when ready and `503` when not ready.

## Readiness Criteria

`/health/ready` currently checks:

- Memory usage threshold (`OPSECHAT_HEALTH_MAX_MEMORY_MB`, default `1024` MB)
- Chat runtime health counters availability

If memory exceeds the configured threshold, readiness returns:

- HTTP `503`
- JSON status: `"not_ready"`

## Example Responses

### `/health/live`

```json
{
  "status": "alive",
  "timestamp": "2026-03-16T00:00:00.000000",
  "version": "0.8.0-alpha"
}
```

### `/health/ready`

```json
{
  "status": "ready",
  "timestamp": "2026-03-16T00:00:00.000000",
  "version": "0.8.0-alpha",
  "uptime_seconds": 123.4,
  "checks": {
    "memory_usage": "ok",
    "chat_runtime": "ok"
  },
  "limits": {
    "max_memory_mb": 1024.0
  },
  "runtime": {
    "active_rooms": 0,
    "active_direct_messages": 0,
    "rate_limited_sessions": 0
  }
}
```
