# Monitoring Guide

This guide describes the built-in runtime monitoring endpoints exposed by OpSecChat.

## Endpoints

### `GET /health`

Returns a lightweight service health payload.

Example fields:

- `status`: health state (`healthy`)
- `timestamp`: UTC timestamp
- `uptime_seconds`: process uptime
- `version`: value from the `VERSION` file
- `active_rooms`: active room count (currently a fixed compatibility field)

### `GET /health/metrics`

Returns summarized in-memory application metrics collected at request time.

Example sections:

- `requests`
  - `total`
  - `error_rate`
  - `avg_response_time`
- `tor`
  - `connection_success_rate`
  - `hidden_service_success_rate`
- `activity`
  - `chat_messages`
  - `emails_composed`
  - `burner_emails`

## Notes

- Metrics are in-memory and reset on process restart.
- The payload is intentionally summarized to avoid exposing sensitive request data.
- Request counters include all HTTP endpoints, including health checks.
