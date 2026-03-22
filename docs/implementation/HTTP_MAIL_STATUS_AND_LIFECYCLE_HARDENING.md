# HTTP Mail Status API and Lifecycle Hardening

Date: 2026-03-22  
Author: Automation Agent

## Summary

This update extends the HTTP-mail subsystem with an authenticated status API and
completes mailbox-destruction hardening so stale mailbox references cannot
accept writes after destruction.

## What Changed

### 1) Mailbox destruction hardening

File: `http_mail_system.py`

- Added explicit mailbox lifecycle state:
  - `HttpMailbox.destroyed` is now initialized as `False`.
- `HttpMailbox.add_message(...)` now returns `None` when mailbox is destroyed.
- `HttpMailbox.delete_message(...)` now rejects deletes on destroyed mailboxes.
- `HttpMailbox.get_messages(...)` returns an empty list for destroyed mailboxes
  after key verification.
- `HttpMailStorage.delete_mailbox(...)` now always:
  - acquires `mailbox.lock`,
  - overwrites all message bodies in memory,
  - clears message list,
  - marks mailbox as `destroyed = True`.

This closes a race window where stale mailbox references could continue to be
used after storage-level deletion.

### 2) New authenticated mailbox status endpoint

File: `http_mail_routes.py`

Added:

- `GET /<path>/mail/<address>/status?key=<read_key>`

Behavior:

- `404` if mailbox address does not exist.
- `403` if `read_key` is invalid.
- `200` JSON with mailbox metadata if authorized:
  - `address`
  - `created_at`
  - `mailbox_age_seconds`
  - `message_count`
  - `oldest_message_at`
  - `newest_message_at`
  - `message_expiry_hours`
  - `destroyed`

### 3) UI support for status checks

File: `templates/http_mail.html`

- Added a "Check Mailbox Status" button in the read section.
- Added client-side `fetchStatus()` function to render mailbox metadata without
  exposing message bodies.

### 4) Small cleanup in email routes

File: `email_routes.py`

- Removed duplicated email lookup in `email_view`.
- Replaced undefined helper usage with direct session initialization.

## Test Coverage Added

File: `tests/test_http_mail.py`

- `test_destroyed_mailbox_rejects_stale_writes`
- `test_mailbox_status_correct_key`
- `test_mailbox_status_wrong_key_forbidden`
- `test_mailbox_status_nonexistent_mailbox`

These tests verify both the new API behavior and the destruction-state write
rejection path.
