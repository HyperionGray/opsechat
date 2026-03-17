# Health and Readiness Checks

This project exposes two operational endpoints:

- `GET /health` for diagnostics
- `GET /ready` for readiness probes

Both endpoints return JSON and are intended for deployment monitoring.

## `GET /health`

Always returns HTTP `200` and reports current service state and check details.

Example response:

```json
{
  "status": "healthy",
  "timestamp": "2026-03-17T21:00:00.000000",
  "uptime_seconds": 123.45,
  "version": "0.8.0-alpha",
  "active_rooms": 1,
  "checks": {
    "tor_connection": {
      "status": "unknown",
      "required": false,
      "control_port": 9051,
      "message": "Tor not required and control port is unreachable"
    },
    "memory_usage": {
      "status": "ok",
      "used_mb": 75.2,
      "max_allowed_mb": 1024.0
    },
    "disk_space": {
      "status": "ok",
      "free_mb": 10240.0,
      "min_required_mb": 100.0,
      "total_mb": 51200.0,
      "used_mb": 40960.0
    }
  }
}
```

Overall `status` is derived from check results:

- `healthy`: no failing checks
- `degraded`: one or more warning checks
- `unhealthy`: one or more failing checks

## `GET /ready`

Returns:

- HTTP `200` when service is ready
- HTTP `503` when one or more critical checks fail

The response includes:

- `ready` boolean
- `failed_checks` list
- `health_status` snapshot
- full `checks` details

## Environment Variables

Tune thresholds with these variables:

- `OPSECHAT_HEALTH_MAX_MEMORY_MB` (default: `1024`)
- `OPSECHAT_HEALTH_MIN_DISK_FREE_MB` (default: `100`)
- `OPSECHAT_HEALTH_SOCKET_TIMEOUT_SECONDS` (default: `0.25`)
- `OPSECHAT_REQUIRE_TOR` (`true/false`, default: `false`)
- `TOR_CONTROL_PORT` (default: `9051`)

## Suggested Usage

- Use `/health` for dashboards and diagnostics.
- Use `/ready` for orchestration readiness probes (Kubernetes, systemd health checks, reverse proxies).
