## HTTP Mail hardening and repo cleanup (2026-03-22)

### What was implemented

1. HTTP mailbox destruction hardening in `http_mail_system.py`
   - Added an explicit `destroyed` state on `HttpMailbox`.
   - Updated `add_message()` to reject writes when a mailbox has been destroyed.
   - Updated `get_messages()` to return an empty list for valid keys on destroyed mailboxes.
   - Updated `delete_message()` and `message_count()` to respect the destroyed state.
   - Removed stale in-code checklist comments by implementing the guard directly.

2. HTTP send route safety in `http_mail_routes.py`
   - Added handling for the rare case where a mailbox is destroyed between lookup and send.
   - Route now returns `410 Gone` when a send is attempted against a mailbox that is no longer writable.

3. Production frontend dependency completion
   - Replaced placeholder `static/jquery.js` with the real jQuery 3.7.1 minified asset.
   - This restores expected jQuery behavior in templates that use `$()` and jQuery APIs.

### Test coverage added

- `tests/test_http_mail.py`
  - `test_add_message_rejected_when_destroyed`
  - `test_get_messages_destroyed_returns_empty_for_valid_key`
  - `test_send_to_destroyed_mailbox_returns_410`

### Repository cleanup

- Removed stray one-off debug scripts from repo root:
  - `test-ci-fix.js`
  - `test_fix.sh`

These scripts were not referenced by project workflows or runtime code and added noise at the repository root.
