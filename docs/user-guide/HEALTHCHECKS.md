# Health and Readiness Endpoints

OpSecChat exposes lightweight operational endpoints for local checks, deployment probes, and service monitoring.

## Endpoints

### `GET /health`
Returns a compact health payload:

```json
{
  "status": "healthy",
  "version": "0.8.0-alpha",
  "active_rooms": 0
}
```

### `GET /health?details=true`
Returns a diagnostic payload that includes runtime metadata and basic checks:

```json
{
  "status": "healthy",
  "version": "0.8.0-alpha",
  "active_rooms": 0,
  "timestamp": "2026-03-15T12:34:56.789012",
  "uptime_seconds": 42.5,
  "checks": {
    "tor_connection": "unknown",
    "memory_usage": "ok",
    "disk_space": "ok"
  }
}
```

### `GET /ready` and `GET /health/ready`
Both endpoints return readiness status for orchestrators:

```json
{
  "status": "ready",
  "service": "opsechat",
  "version": "0.8.0-alpha"
}
```

## Notes

- `/health` is intended for simple external checks and dashboards.
- `/ready` and `/health/ready` are intended for readiness/liveness probes.
- Version is read from the repository `VERSION` file.
