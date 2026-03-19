# Health, Readiness, and Liveness Endpoints

## Overview

OpSecChat now exposes three operational endpoints:

- `GET /health` - detailed runtime health snapshot
- `GET /health/ready` - readiness probe for load balancers/orchestrators
- `GET /health/live` - lightweight liveness probe

These endpoints are designed to be safe for production probes and avoid
returning sensitive user data.

## Endpoint Semantics

### `/health`

Returns a richer operational summary:

- `status`: `healthy` or `degraded`
- `timestamp`
- `uptime_seconds`
- `version`
- `active_rooms`
- `active_direct_messages`
- `rate_limited_sessions`
- `checks`:
  - `version_file` (`ok` or `degraded`)
  - `chat_store_access` (`ok` or `unavailable`)
  - `memory_usage`
  - `disk_space`
  - `tor_connection` (`unknown` unless explicitly probed)

### `/health/ready`

Readiness is intended for traffic-gating decisions:

- Returns HTTP `200` when core checks pass (`status: "ready"`).
- Returns HTTP `503` when a core check fails (`status: "not_ready"`).

Current required checks:

- `version_file == "ok"`
- `chat_store_access == "ok"`

### `/health/live`

Liveness is intentionally lightweight:

- Returns HTTP `200` when process uptime is sane (`status: "alive"`).
- Returns HTTP `503` if liveness cannot be confirmed (`status: "unhealthy"`).

## Example Probe Commands

```bash
curl -sS http://127.0.0.1:5000/health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/health/ready
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/health/live
```

## Notes

- Endpoint payloads avoid exposing message contents, usernames, session IDs, or
  other sensitive fields.
- Runtime chat counters are best-effort. If chat state modules are unavailable,
  safe fallback values are returned and readiness may report `not_ready`.
