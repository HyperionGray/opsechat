# Health Check Endpoints

This project exposes Kubernetes/systemd-friendly health endpoints for runtime monitoring.

## Endpoints

### `GET /health/live`

Liveness probe. Confirms the process is running and responsive.

- Expected status code: `200`
- Typical use: restart dead/stuck containers

Example response:

```json
{
  "status": "alive",
  "timestamp": "2026-03-19T09:00:00.000000",
  "uptime_seconds": 123.45,
  "version": "0.8.0-alpha"
}
```

### `GET /health/ready`

Readiness probe. Confirms required in-memory subsystems are available.

- Expected status code: `200` when ready, `503` when not ready
- Typical use: load balancer routing / service readiness gates

Checks include:

- VERSION file availability
- Simple chat in-memory room storage access
- In-memory rate limiter storage access
- Optional memory pressure check (`psutil`, warning threshold)

Example response:

```json
{
  "status": "ready",
  "ready": true,
  "timestamp": "2026-03-19T09:00:00.000000",
  "checks": {
    "version": {"status": "ok", "required": true, "details": "version=0.8.0-alpha"},
    "chat_storage": {"status": "ok", "required": true, "details": "active_rooms=0"},
    "rate_limiter_store": {"status": "ok", "required": true, "details": "tracked_sessions=0"},
    "memory_usage": {"status": "ok", "required": false, "details": "rss_mb=73.2"}
  }
}
```

### `GET /health`

Composite health endpoint for dashboards.

- Returns application-level status (`healthy`, `degraded`, `unhealthy`)
- Includes readiness (`ready`) and active room count

## Memory Warning Threshold

Optional memory warning threshold can be tuned with:

```bash
OPSECHAT_HEALTH_MEMORY_WARN_MB=1536
```

If memory exceeds this threshold, `/health` may report `degraded` while `/health/ready` can still remain ready.
