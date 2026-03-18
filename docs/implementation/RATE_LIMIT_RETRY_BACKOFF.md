# Rate Limit Retry Metadata and Client Backoff

## Summary

Simple chat endpoints now provide explicit retry metadata when throttled, and the web UI performs bounded automatic retries with backoff for transient 429 responses.

## What Changed

### Backend

- Added standardized 429 JSON payloads in `simple_chat_routes.py` via `build_rate_limit_response(...)`.
- Manual rate-limit responses now include:
  - `error`
  - `retry_after` (seconds)
  - `retryable` (`true`)
  - `limit_key` (logical endpoint name)
- Added `Retry-After` response header for manual rate limits.
- Added a Flask `@app.errorhandler(429)` in `app_factory.py` so Flask-Limiter-triggered throttles on `/chat/*` also return retry metadata and a `Retry-After` header.

### Frontend

- `templates/simple_chat_index.html`:
  - Room creation now retries up to 2 times on 429.
  - Uses server `Retry-After` or `retry_after` JSON for wait duration.
- `templates/simple_chat_room.html`:
  - Message send now retries up to 2 times on 429.
  - Displays user-facing status during backoff waits.
  - Keeps final error surfaced when retry budget is exhausted.

## Why

- Aligns chat UX with existing endpoint throttling.
- Reduces transient user-facing failures under short bursts.
- Provides deterministic retry timing to clients instead of blind polling.

## Tests Added

In `tests/test_rate_limit_and_health.py`:

- `test_build_rate_limit_response_sets_json_and_retry_header`
- `test_chat_create_429_includes_retry_metadata_from_error_handler`

These cover both manual rate-limit responses and Flask-Limiter 429 handling for chat endpoints.
