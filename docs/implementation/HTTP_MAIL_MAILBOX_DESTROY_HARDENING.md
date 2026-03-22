# HTTP Mailbox Destroy Hardening (2026-03-22)

## Summary

Completed the unfinished mailbox-destroy follow-up in the HTTP mail system by enforcing a mailbox-level destroyed state under lock.

## What changed

### 1) `HttpMailbox` now tracks destroyed state
- Added `self.destroyed` flag in `HttpMailbox`.
- `add_message(...)` now returns `None` if the mailbox is already destroyed.
- `delete_message(...)` now fails fast when mailbox is destroyed.

### 2) `HttpMailStorage.delete_mailbox(...)` hardened
- After auth and removal from global mapping, deletion now:
  - Acquires `mailbox.lock`
  - Sets `mailbox.destroyed = True`
  - Overwrites all message contents in memory
  - Clears message list

This guarantees stale object references cannot accept future writes after destroy.

### 3) Route behavior updated for edge case
- `POST /<path>/mail/<address>/send` now returns:
  - `410 Gone` with JSON `{ "error": "Mailbox has been destroyed" }`
  - or equivalent UI error for non-JSON requests
when a concurrent destroy happened after lookup.

## Tests added

- `test_delete_mailbox_marks_instance_destroyed`
- `test_add_message_returns_none_when_destroyed`

These verify post-destroy writes are denied and message storage stays empty.
