# Monitoring and Health Endpoints

OpSecChat exposes lightweight operational endpoints for liveness, readiness, and basic service metrics.

These endpoints are intended for:

- container health checks
- simple uptime monitors
- dashboard integrations that do not require Prometheus

## Endpoints

### `GET /health`

Returns a general service health payload.

Example fields:

- `status`: overall status (`healthy`)
- `timestamp`: UTC timestamp
- `uptime_seconds`: process uptime
- `version`: value from `VERSION`
- `active_rooms`: integer count
- `checks`: basic subsystem checks

### `GET /health/live`

Liveness probe endpoint.

Response:

```json
{"status":"alive"}
```

Use this endpoint to verify the process is responsive.

### `GET /health/ready`

Readiness probe endpoint.

Response:

```json
{
  "status": "ready",
  "checks": {
    "tor_connection": "unknown",
    "memory_usage": "ok",
    "disk_space": "ok"
  }
}
```

Returns HTTP `200` when ready and HTTP `503` when not ready.

### `GET /health/metrics`

Returns summarized in-memory APM metrics:

- request totals
- error rate
- average response time
- Tor success rates
- chat/email activity counters

Example fields:

```json
{
  "timestamp": "2026-03-19T18:00:00.000000",
  "uptime_seconds": 123.45,
  "requests": {
    "total": 42,
    "error_rate": 0.0,
    "avg_response_time": 0.01
  },
  "tor": {
    "connection_success_rate": 100.0,
    "hidden_service_success_rate": 100.0
  },
  "activity": {
    "chat_messages": 12,
    "emails_composed": 3,
    "burner_emails": 5
  }
}
```

## Notes

- Metrics are process-local and reset on restart.
- This endpoint is JSON-based and intentionally minimal.
- For long-term historical monitoring, forward logs/metrics to external infrastructure.
