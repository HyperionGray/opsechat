## HTTP Mail Lifecycle Hardening

Date: 2026-03-23  
Scope: `http_mail_system.py`, `http_mail_routes.py`, `email_routes.py`, `tests/test_http_mail.py`

### Summary

This update completes unfinished mailbox-destruction follow-ups in the HTTP mail subsystem and cleans up a fragile route path in the email routes module.

### What Changed

1. Mailbox destruction is now explicit and final:
   - `HttpMailbox` has a `destroyed` lifecycle flag.
   - `HttpMailbox.destroy()` securely overwrites and clears all messages, then marks the mailbox destroyed.
   - `HttpMailStorage.delete_mailbox()` now removes the mailbox from global storage and then calls `mailbox.destroy()`.

2. Stale mailbox references are now safe:
   - `HttpMailbox.add_message()` returns `None` when called on a destroyed mailbox.
   - `HttpMailbox.get_messages()` returns an empty list for destroyed mailboxes after key validation.
   - `HttpMailbox.message_count()` returns `0` when destroyed.

3. Route behavior for destroyed mailbox writes:
   - `http_mail_routes.py` checks for `None` from `add_message()` and returns HTTP `410 Gone` with a JSON error.

4. Email route cleanup:
   - Added local `_ensure_session()` helper in `email_routes.py`.
   - Removed duplicate `get_email()` call in `email_view`.
   - This prevents runtime failures when the route is hit without a pre-populated session.

### Test Coverage Added

In `tests/test_http_mail.py`:

- `test_delete_mailbox_marks_stale_reference_destroyed`
  - Verifies stale mailbox references are marked destroyed and cannot accept new messages.
- `test_destroyed_mailbox_rejects_new_messages`
  - Verifies direct writes to a destroyed mailbox are blocked.
- `test_view_email_without_session_returns_404_not_500`
  - Verifies `email_view` handles missing session safely and does not crash.

### Security and Reliability Impact

- Improves data hygiene by enforcing secure wipe on mailbox destruction.
- Prevents race-adjacent stale-reference writes after mailbox teardown.
- Reduces route fragility by removing undefined-helper behavior.
