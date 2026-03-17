# Request Metrics Endpoint

## Summary

OpSecChat now exposes a lightweight operational metrics endpoint:

- `GET /metrics`

This endpoint reports aggregated runtime telemetry collected in-process from Flask request handling. It is intended for local diagnostics, container health tooling, and lightweight monitoring setups.

## What It Includes

The payload is intentionally aggregate-only and excludes per-user identifiers:

- Request totals
- Request error rate
- Average response time (ms)
- P95 response time (ms)
- Top endpoints by request volume
- Uptime and memory usage
- High-level activity counters (chat/email/burner totals)

Example shape:

```json
{
  "status": "ok",
  "timestamp": "2026-03-17T18:00:00.000000",
  "requests": {
    "total": 42,
    "error_rate": 4.76,
    "avg_response_time_ms": 18.24,
    "p95_response_time_ms": 60.11,
    "tracked_endpoints": 5,
    "top_endpoints": [
      {
        "endpoint": "GET /health",
        "count": 12,
        "error_rate": 0.0,
        "avg_response_time_ms": 4.37
      }
    ]
  },
  "runtime": {
    "uptime_seconds": 321.77,
    "memory_usage_mb": 58.42
  },
  "activity": {
    "chat_messages": 0,
    "emails_composed": 0,
    "burner_emails": 0
  }
}
```

## Notes

- Metrics are in-memory and reset on process restart.
- The endpoint is read-only and does not change application state.
- Request telemetry capture is best-effort; any monitoring failures are ignored to avoid impacting request handling.
