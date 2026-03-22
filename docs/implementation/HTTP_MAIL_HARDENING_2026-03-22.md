# HTTP Mail Hardening Update (2026-03-22)

## Summary

This update continues the email-over-HTTP direction by hardening mailbox destruction behavior and closing a route-level session bug.

## Changes

### 1) Mailbox destruction safety (http_mail_system.py)

- Added an explicit `destroyed` state to `HttpMailbox`.
- Added `HttpMailbox.destroy()` to securely overwrite message content, clear in-memory message objects, and permanently block future writes.
- Updated `HttpMailbox.add_message()` to return `None` when a mailbox is destroyed.
- Updated read/delete/count paths to handle destroyed state safely.
- Simplified `HttpMailStorage.delete_mailbox()` to detach mailbox from storage and then call `mailbox.destroy()`.

Result: stale references to a mailbox object can no longer append new messages after destruction.

### 2) HTTP send route behavior (http_mail_routes.py)

- Added a guard in `POST /<path>/mail/<address>/send`:
  - returns `410 Gone` when a mailbox exists as a stale reference but is already destroyed.

### 3) Email route stability (email_routes.py)

- Added missing `_ensure_session()` helper used by `email_view`.
- Removed duplicated email lookup in `email_view`.

Result: prevents a runtime `NameError` path when viewing email without a preexisting session.

### 4) Test coverage

Extended `tests/test_http_mail.py` with:

- deleted mailbox references rejecting new writes
- destroyed mailbox rejecting adds
- email view path without session returning expected 404 (instead of crashing)

## Notes

- No protocol/API contract changes were introduced beyond the new `410` response for destroyed-mailbox send attempts.
- Existing mailbox address/read-key semantics and expiry behavior remain unchanged.
