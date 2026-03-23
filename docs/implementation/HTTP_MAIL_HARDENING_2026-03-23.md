# HTTP Mail Hardening (2026-03-23)

## Summary

Completed a pending follow-up in the email-over-HTTP implementation by hardening mailbox destruction semantics and concurrent write behavior.

## What changed

### 1) Destroyed mailbox guard in `HttpMailbox`

- Added a `destroyed` state flag to mailbox objects.
- Added `HttpMailbox.destroy()` to:
  - overwrite all in-memory message fields,
  - clear the message list,
  - permanently disable future writes through stale references.

### 2) Safe write behavior after mailbox destruction

- `HttpMailbox.add_message(...)` now returns `None` if the mailbox is already destroyed.
- `HttpMailbox.get_messages(...)` returns an empty list for a destroyed mailbox with a valid key.
- `HttpMailbox.delete_message(...)` now fails (`False`) for destroyed mailboxes.

### 3) Storage deletion path now uses mailbox-level destroy

- `HttpMailStorage.delete_mailbox(...)` now removes the mailbox from global storage and then calls `mailbox.destroy()` to centralize secure cleanup logic.

### 4) HTTP route behavior for race conditions

- `POST /<path>/mail/<address>/send` now returns `410 Gone` if a mailbox becomes unavailable/destroyed during request handling (for example, concurrent destroy vs send race).

## Tests added

Added regression coverage in `tests/test_http_mail.py`:

- deleting a mailbox disables stale mailbox references from accepting new messages,
- destroying a mailbox blocks new writes,
- destroying a mailbox clears previously stored messages,
- send route returns `410` for destroyed mailbox references.

## Why this matters

This closes a real consistency and security gap: mailbox objects that were removed from global storage can no longer be used as writable stale references in concurrent paths.
