# Monitoring and Health Endpoints

This document describes the runtime health and metrics endpoints exposed by OpSecChat.

## Endpoints

### `GET /health`

Returns a lightweight service health payload suitable for liveness checks.

Example:

```json
{
  "status": "healthy",
  "timestamp": "2026-03-17T12:34:56.000000",
  "uptime_seconds": 123.45,
  "version": "0.8.0-alpha",
  "active_rooms": 1,
  "checks": {
    "tor_connection": "unknown",
    "memory_usage": "ok",
    "disk_space": "ok"
  }
}
```

### `GET /health/metrics`

Returns aggregate in-memory application metrics.

Example:

```json
{
  "timestamp": "2026-03-17T12:34:56.000000",
  "uptime_seconds": 123.45,
  "requests": {
    "total": 42,
    "error_rate": 0.0,
    "avg_response_time": 0.012
  },
  "tor": {
    "connection_success_rate": 100.0,
    "hidden_service_success_rate": 100.0
  },
  "activity": {
    "chat_messages": 5,
    "emails_composed": 2,
    "burner_emails": 1
  }
}
```

### `GET /health/metrics?detailed=true`

Returns the same aggregate summary plus per-endpoint request stats.

Example `requests.by_endpoint` payload:

```json
{
  "GET /health": {
    "count": 3,
    "avg_response_time": 0.001,
    "error_rate": 0.0
  },
  "GET /health/metrics": {
    "count": 2,
    "avg_response_time": 0.002,
    "error_rate": 0.0
  }
}
```

## Notes

- Metrics are in-memory and reset when the process restarts.
- Request timing is collected in Flask middleware and does not block request handling.
- Monitoring is best-effort: metrics failures are ignored so user-facing traffic is unaffected.
