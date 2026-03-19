# Rate Limit Retry and Backoff (Simple Chat)

## Summary

Simple chat write endpoints now return a consistent rate-limit contract and the chat room UI now performs bounded retry with exponential backoff when it receives HTTP `429`.

This closes an open TODO for retry/backoff behavior on top of existing rate limits.

## What Changed

### 1) Consistent 429 API payload and headers

Updated `simple_chat_routes.py` to return structured retry metadata from:

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

New response fields when limited:

- `error`: human-readable message
- `retry_after`: server-advised minimum wait time (seconds)
- `backoff_seconds`: server-computed exponential backoff hint (seconds)

New response headers when limited:

- `Retry-After`
- `X-Backoff-Seconds`

### 2) Client-side retry and exponential backoff

Updated `templates/simple_chat_room.html`:

- On `429` from message send, client waits and retries automatically.
- Delay is derived from server metadata (`retry_after`/`backoff_seconds`) with safe fallback calculation.
- Retries are bounded to avoid infinite loops.
- Status line shows retry progress to the user.
- Duplicate submits are prevented while a send is in flight.

### 3) Tests

Updated `tests/test_rate_limit_and_health.py`:

- Added unit coverage for exponential backoff growth/cap.
- Added integration coverage that verifies `429` payload contract and retry headers on `/chat/dm/send`.

## Behavior Notes

- Backoff is bounded to keep UI responsive and predictable.
- Input is only cleared after a successful send.
- Non-`429` send failures are surfaced immediately without retry loops.

## Cleanup Included

- Removed stale duplicate file: `tests/mock_server_refactored.py`.
- Replaced no-op `pass` stubs in `tests/mock_server.py` fallback mocks with concrete test-safe return values.
