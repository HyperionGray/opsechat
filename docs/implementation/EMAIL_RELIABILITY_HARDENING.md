# Email Reliability Hardening (March 2026)

## Summary

This update hardens the email subsystem in three areas:

1. **HTTP mailbox destruction safety**
2. **Burner email ownership enforcement**
3. **Repository cleanup of stale duplicate fixture code**

## What Changed

### 1) HTTP Mailbox destruction is now authoritative

Files:
- `http_mail_system.py`
- `http_mail_routes.py`

Changes:
- Added a `destroyed` state to `HttpMailbox`.
- Added `HttpMailbox.destroy()` to securely overwrite and clear all message data.
- `HttpMailStorage.delete_mailbox()` now removes the mailbox from storage and calls `destroy()`.
- `HttpMailbox.add_message()`, `get_messages()`, and `delete_message()` now refuse operations on destroyed mailboxes.
- `POST /<path>/mail/<address>/send` now returns **410 Gone** if a mailbox becomes unavailable between lookup and write.

Why:
- Prevents race-style stale-reference writes after mailbox destruction.
- Makes mailbox deletion behavior consistent and explicit.

### 2) Burner operations are owner-scoped

Files:
- `email_system.py`
- `email_routes.py`

Changes:
- `BurnerEmailManager.expire_burner()` now supports optional owner validation (`user_id`).
- `rotate_burner()` now returns `None` when asked to rotate a burner not owned by the caller.
- Added `is_user_burner()` for lightweight ownership checks.
- Fixed `cleanup_expired()` to correctly remove entries from both:
  - `burner_addresses`
  - `user_burners` index
- Added `get_user_stats()` used by burner list JSON route.
- Burner routes now enforce ownership for rotate/expire and return **404** for non-owned burners.
- Added route alias `/<path>/email/burner/list` in addition to `list.json` (matches current frontend JS).

Why:
- Prevents cross-user burner manipulation.
- Keeps in-memory indexes consistent over time.
- Restores burner list auto-refresh route compatibility.

### 3) Stale file cleanup

Removed:
- `tests/mock_server_refactored.py`

Reason:
- File was an unreferenced duplicate of `tests/mock_server.py`.
- Removal reduces maintenance overhead and repository noise.

Also updated:
- `tests/mock_server.py` fallback mock classes now have concrete behavior instead of stub `pass` methods.

## Test Coverage Added

Updated tests:
- `tests/test_http_mail.py`
  - Destroyed mailbox rejects stale reference usage
  - Burner ownership route protections
  - Burner list alias route
  - Session bootstrap regression coverage for email view route
- `tests/test_email_system.py`
  - Expire/rotate ownership checks
  - Index cleanup correctness
  - `get_user_stats()` response shape

