# Health and Metrics Endpoints

OpSecChat exposes lightweight operational endpoints for service monitoring.

## Endpoints

### `GET /health`
Backward-compatible aggregate health status.

- `status`: `healthy` or `degraded`
- `uptime_seconds`
- `version`
- `checks` summary

### `GET /health/live`
Liveness probe for process-level availability.

- `status`: always `alive` while the app is running
- `timestamp`
- `uptime_seconds`
- `version`

### `GET /health/ready`
Readiness probe for load balancers and orchestrators.

- Returns `200` when ready, `503` when degraded
- Includes:
  - `ready` boolean
  - `checks.version_file`
  - `checks.disk_space`
  - `checks.memory_usage`

### `GET /metrics`
JSON metrics snapshot from in-memory APM counters.

Includes:
- Request totals, error counts, average response time
- Per-endpoint request breakdown (`method + path`)
- Chat/email activity counters
- Tor event counters
- Basic system metrics (`memory_usage_mb`, `uptime_seconds`)

## Example

```bash
curl -s http://127.0.0.1:5000/health
curl -s http://127.0.0.1:5000/health/live
curl -s http://127.0.0.1:5000/health/ready
curl -s http://127.0.0.1:5000/metrics
```

## Notes

- Metrics are in-memory and reset on process restart.
- No sensitive payload fields (user IDs, tokens, emails, session IDs) are emitted.
