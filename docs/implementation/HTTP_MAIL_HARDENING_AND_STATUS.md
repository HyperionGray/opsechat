# HTTP Mail Hardening and Status Endpoint

Date: 2026-03-22

## Summary

This update continues the recent email-over-HTTP work by finishing destruction-safety follow-ups and adding a lightweight owner metadata API.

## What changed

### 1) Mailbox destruction hardening

Files:
- `http_mail_system.py`

Changes:
- `HttpMailbox` now tracks a `destroyed` state.
- `HttpMailbox.add_message(...)` now rejects writes after destruction and returns `None`.
- `HttpMailbox.delete_message(...)` and `message_count()` now honor destroyed state.
- `HttpMailStorage.delete_mailbox(...)` marks mailbox as destroyed under mailbox lock before scrubbing/clearing messages, preventing stale references from writing during delete.

Security effect:
- Reduces race-window risk during mailbox destruction.
- Ensures stale in-process references cannot append messages after mailbox deletion.

### 2) New authenticated mailbox status endpoint

Files:
- `http_mail_routes.py`
- `http_mail_system.py`

Endpoint:
- `GET /<path>/mail/<address>/status?key=<read_key>`

Response (JSON):
- `address`
- `created_at` (ISO timestamp)
- `message_count`
- `destroyed`
- `expiry_hours`

Purpose:
- Allows mailbox owners to poll metadata without downloading full message bodies.

### 3) Cleanup fixes

Files:
- `email_routes.py`
- `docs/README.md`

Changes:
- Removed a duplicate email lookup in `email_view`.
- Replaced invalid `_ensure_session()` call in `email_view` with in-function session initialization.
- Removed stale "(TODO)" text from docs quick-start index line.

## Tests added/updated

File:
- `tests/test_http_mail.py`

Coverage additions:
- Destroyed mailbox rejects writes from stale mailbox references.
- Status endpoint returns metadata for valid read key.
- Status endpoint rejects invalid read key.
