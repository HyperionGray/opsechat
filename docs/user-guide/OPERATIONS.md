# Operations Guide

This guide covers lightweight operational checks for running OpSecChat services.

## Health Endpoints

OpSecChat exposes two monitoring endpoints:

- `GET /health` - Detailed runtime health snapshot
- `GET /health/ready` - Readiness probe suitable for load balancers/orchestrators

### `GET /health`

Returns HTTP `200` with a JSON payload that includes:

- `status` (`healthy`)
- `service` (`opsechat`)
- `version` (from `VERSION`)
- `timestamp_utc` (RFC3339 UTC)
- `uptime_seconds`
- `active_rooms`
- `active_direct_messages`
- `rate_limiter_sessions`
- `cleanup_thread_alive`

Example:

```json
{
  "status": "healthy",
  "service": "opsechat",
  "version": "0.8.0-alpha",
  "timestamp_utc": "2026-03-15T03:20:00Z",
  "uptime_seconds": 1234,
  "active_rooms": 2,
  "active_direct_messages": 1,
  "rate_limiter_sessions": 5,
  "cleanup_thread_alive": true
}
```

### `GET /health/ready`

Returns:

- HTTP `200` with `{"status":"ready", ...}` when background cleanup is running
- HTTP `503` with `{"status":"not_ready", ...}` if the process is not fully ready

This endpoint is ideal for readiness checks in container orchestrators.

## Basic Monitoring Commands

```bash
curl -s http://127.0.0.1:5000/health | python -m json.tool
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/health/ready
```
