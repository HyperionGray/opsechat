# Monitoring Guide

This guide documents the built-in operational endpoints for OpSecChat.

## Endpoints

### `GET /health`

Returns a lightweight service health payload intended for liveness checks.

Example response fields:

- `status`: service status (`healthy`)
- `timestamp`: current UTC timestamp
- `uptime_seconds`: process uptime
- `version`: application version from `VERSION`
- `active_rooms`: current room count abstraction (currently fixed at `1`)

### `GET /metrics`

Returns structured runtime metrics collected in memory.

Default response includes:

- `status`: endpoint status (`ok`)
- `timestamp`: current UTC timestamp
- `summary`: high-level aggregates
  - request totals
  - request error rate
  - average response time
  - chat/email activity counters
  - Tor operation success rates

By default, endpoint-level request breakdown is also returned under:

- `requests_by_endpoint`

Each endpoint entry contains:

- `count`
- `errors`
- `error_rate`
- `avg_response_time`

## Query Parameters (`/metrics`)

- `include_endpoints` (optional)
  - default: `true`
  - set to `false`, `0`, or `no` to omit endpoint breakdown
- `top_n` (optional)
  - default: `20`
  - limits number of endpoint entries returned

## Examples

```bash
curl -s http://127.0.0.1:5000/health
curl -s http://127.0.0.1:5000/metrics
curl -s "http://127.0.0.1:5000/metrics?include_endpoints=false"
curl -s "http://127.0.0.1:5000/metrics?top_n=5"
```

## Notes

- Metrics are process-local and stored in memory.
- Counters reset when the service restarts.
- This endpoint is intended for internal observability and deployment checks.
