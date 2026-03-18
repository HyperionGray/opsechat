# Health Checks

This document describes the operational health endpoints exposed by OpSecChat.

## Endpoints

### `GET /health`

Backward-compatible aggregate health endpoint.

- Returns `200 OK`
- Status values:
  - `healthy` when readiness checks pass
  - `degraded` when readiness checks fail

Use this when existing tooling already points to `/health`.

### `GET /healthz`

Liveness probe endpoint.

- Returns `200 OK` when the process is alive
- Lightweight payload intended for orchestrators and uptime checks

Use this for "is the process up?" checks.

### `GET /readyz`

Readiness probe endpoint.

- Returns `200 OK` when the app is ready to serve requests
- Returns `503 Service Unavailable` when required checks fail

Current readiness checks include:

- VERSION file is available
- APM start-time metric is initialized
- Critical routes are registered (`/health`, `/chat`, `/chat/create`, `/chat/dm/send`)

Use this for load balancers and deployment rollouts.

## Example Responses

### Ready

```json
{
  "status": "ready",
  "timestamp": "2026-03-18T03:15:00.000000",
  "uptime_seconds": 42.1,
  "version": "0.8.0-alpha",
  "checks": {
    "version_file": {"status": "ok"},
    "apm_initialized": {"status": "ok"},
    "critical_routes_registered": {"status": "ok"}
  },
  "not_ready_checks": []
}
```

### Not Ready

```json
{
  "status": "not_ready",
  "not_ready_checks": ["critical_routes_registered"]
}
```
