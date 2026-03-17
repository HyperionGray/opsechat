# Rate Limiting Guide

This document describes chat endpoint rate limiting in OpSecChat and how to tune it for different environments.

## Overview

Simple chat write endpoints use two layers:

1. Flask-Limiter decorators on HTTP routes.
2. An in-process per-session sliding-window limiter in `simple_chat_routes.py`.

The in-process limiter now includes adaptive backoff: repeated limit violations increase cooldown time.

## Default Limits

The in-process limiter defaults are:

- `chat_create`: 10 requests / 60 seconds
- `chat_message`: 30 requests / 60 seconds
- `dm_send`: 5 requests / 60 seconds

Adaptive backoff defaults:

- Backoff base: 5 seconds
- Backoff max: 300 seconds

When a client exceeds an endpoint limit, the retry delay is:

`window_retry + adaptive_penalty`

Where adaptive penalty grows exponentially on repeated violations and decays after successful requests.

## Environment Configuration

Set these environment variables before starting the server:

| Variable | Purpose | Default |
|---|---|---|
| `OPSECHAT_CHAT_CREATE_MAX_REQUESTS` | Max create-room requests per window | `10` |
| `OPSECHAT_CHAT_CREATE_WINDOW_SECONDS` | Create-room window size | `60` |
| `OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS` | Max room-message posts per window | `30` |
| `OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS` | Room-message window size | `60` |
| `OPSECHAT_DM_SEND_MAX_REQUESTS` | Max direct-message sends per window | `5` |
| `OPSECHAT_DM_SEND_WINDOW_SECONDS` | Direct-message window size | `60` |
| `OPSECHAT_RATE_LIMIT_BACKOFF_BASE_SECONDS` | Initial adaptive penalty | `5` |
| `OPSECHAT_RATE_LIMIT_BACKOFF_MAX_SECONDS` | Max adaptive penalty cap | `300` |

Invalid or missing values safely fall back to defaults.

## Example

```bash
export OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS=45
export OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS=120
export OPSECHAT_RATE_LIMIT_BACKOFF_BASE_SECONDS=10
export OPSECHAT_RATE_LIMIT_BACKOFF_MAX_SECONDS=240
python runserver.py
```

## Validation

Run:

```bash
pytest tests/test_rate_limit_and_health.py -q
```

This test suite validates:

- Sliding-window request enforcement
- Session isolation
- Adaptive backoff escalation on repeated violations
- Environment configuration parsing/fallbacks
