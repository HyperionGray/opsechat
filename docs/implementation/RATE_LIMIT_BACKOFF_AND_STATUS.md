# Rate-Limit Backoff and Status API

## Overview

Chat write endpoints now return a consistent, machine-readable rate-limit response when throttled. This makes client retry behavior deterministic and safer under load.

The following endpoints are covered:

- `POST /chat/create`
- `POST /chat/room/<room_id>/messages`
- `POST /chat/dm/send`

## 429 Response Contract

When a request is rate-limited, the API returns:

- HTTP status `429`
- `Retry-After` header (seconds)
- JSON payload:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Maximum 3 room creations per minute. Try again in 42 seconds.",
  "endpoint": "chat_create",
  "retry_after_seconds": 42,
  "limit": {
    "max_requests": 3,
    "window_seconds": 60
  },
  "backoff": {
    "strategy": "exponential",
    "jitter": "full",
    "schedule_seconds": [42, 60, 60]
  }
}
```

## New Status Endpoint

`GET /chat/rate-limit-status`

Returns the current session's usage and remaining quota for each chat write limit:

```json
{
  "limits": {
    "chat_create": {
      "max_requests": 3,
      "window_seconds": 60,
      "used": 1,
      "remaining": 2,
      "retry_after_seconds": 0
    },
    "chat_message": {
      "max_requests": 30,
      "window_seconds": 60,
      "used": 4,
      "remaining": 26,
      "retry_after_seconds": 0
    },
    "dm_send": {
      "max_requests": 5,
      "window_seconds": 60,
      "used": 0,
      "remaining": 5,
      "retry_after_seconds": 0
    }
  },
  "timestamp": "2026-03-18T18:01:10.000000Z"
}
```

## Client Retry Guidance

1. Always respect the `Retry-After` header as the minimum delay.
2. Use the provided `backoff.schedule_seconds` values as baseline retries.
3. Keep jitter enabled client-side to reduce synchronized retry spikes.

## Why This Change

This closes the "backoff/retry logic" gap from the production TODO list by making rate-limit handling explicit and testable for API consumers.
