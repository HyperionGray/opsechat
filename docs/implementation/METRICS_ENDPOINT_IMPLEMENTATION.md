# Metrics Endpoint and Request Instrumentation

## Summary

This update adds lightweight operational observability to the Flask app by:

- adding per-request timing and counting instrumentation in the app factory
- exposing a new `/metrics` JSON endpoint for runtime metrics
- extending the metrics payload with endpoint-level request summaries

The feature is intentionally minimal and read-only so it is safe to expose to internal operators and deployment health tooling.

## What Was Implemented

### 1) Request instrumentation in `app_factory.py`

- Added a `before_request` hook to capture request start time using `time.perf_counter()`.
- Extended the existing `after_request` hook to record:
  - HTTP method
  - request path
  - response status code
  - response time (seconds)
- Metrics collection is wrapped in a `try/except` to ensure metrics failures never break user responses.

### 2) New `/metrics` endpoint

- Added `GET /metrics` route that returns `monitoring.apm.get_metrics_summary()` as JSON.
- Endpoint inherits existing security hardening headers from `after_request`.

### 3) Expanded metrics summary in `monitoring.py`

`ApplicationPerformanceMonitor.get_metrics_summary()` now includes:

- `requests.by_endpoint` map keyed by `"<METHOD> <PATH>"`, with:
  - `count`
  - `avg_response_time`
  - `error_rate` (percentage)
- `system.memory_usage_mb` at top-level summary to aid quick operational checks.

## Tests Added

Updated `tests/test_rate_limit_and_health.py` with:

- `test_metrics_endpoint_returns_200_with_expected_shape`
- `test_metrics_endpoint_tracks_health_requests`
- `test_metrics_endpoint_sets_security_headers`

These validate:

- endpoint availability and JSON structure
- request counter movement after traffic
- security headers and fingerprinting-hardening headers remain intact

## Notes

- The metrics endpoint is JSON only and does not expose secrets.
- Existing sanitization behavior in structured logging remains unchanged.
- Metrics are in-memory and reset on process restart, matching current application patterns.
