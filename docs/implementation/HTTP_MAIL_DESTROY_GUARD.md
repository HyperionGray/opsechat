# HTTP Mail Destroy Guard

## Summary

This update hardens the HTTP mail subsystem against stale in-memory mailbox
references after mailbox destruction.

Before this change, `HttpMailStorage.delete_mailbox()` removed the mailbox from
global storage and scrubbed existing messages, but an already-held Python
reference to the mailbox object could still call `add_message()` and append new
messages in memory.

## What changed

### 1) Explicit destroyed state on mailboxes

- Added `HttpMailbox.destroyed` (default `False`)
- `HttpMailStorage.delete_mailbox()` now sets `mailbox.destroyed = True` while
  holding the mailbox lock before clearing messages

### 2) Write guard for stale references

- `HttpMailbox.add_message(...)` now returns `None` if the mailbox is destroyed
  (instead of creating a message)
- Route handling in `http_mail_routes.py` treats this as mailbox unavailable
  and returns:
  - JSON: `410 Gone` with `"Mailbox is no longer available"`
  - HTML: rendered page with same error and `410` status

### 3) Defensive reads/deletes

- `HttpMailbox.get_messages(...)` returns an empty list for valid keys when the
  mailbox is destroyed
- `HttpMailbox.delete_message(...)` returns `False` when destroyed

## Security and correctness impact

- Prevents post-destroy writes via stale object references
- Keeps deletion behavior deterministic under concurrent access
- Preserves secure memory scrubbing of mailbox contents

## Tests added

In `tests/test_http_mail.py`:

- `test_delete_mailbox_marks_existing_reference_destroyed`
- `test_stale_mailbox_reference_refuses_new_messages_after_destroy`
- `test_destroyed_mailbox_refuses_add_message`
- Route-level stale-reference assertion in
  `test_send_with_stale_reference_after_destroy_returns_gone`

These tests ensure the mailbox object itself refuses writes after destroy, even
outside normal route lookup flow.
