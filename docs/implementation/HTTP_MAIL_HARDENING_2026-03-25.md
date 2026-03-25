# HTTP Mail Hardening and Cleanup (2026-03-25)

## Summary

This update completes unfinished HTTP-mail safety work, adds a compose fallback route for non-JS reliability, and performs repository cleanup of stale/generated files.

## What changed

### 1) Destroyed mailbox write-guard (feature completion)

Updated `http_mail_system.py`:

- Added explicit `destroyed` state to `HttpMailbox`.
- `HttpMailbox.add_message(...)` now checks `destroyed` under mailbox lock and returns `None` if writes are no longer allowed.
- `HttpMailbox.message_count()` returns `0` for destroyed mailboxes.
- `HttpMailbox.get_messages(...)` and `delete_message(...)` deny actions when mailbox is destroyed.
- `HttpMailStorage.delete_mailbox(...)` now:
  - removes mailbox from global map under storage lock,
  - sets `mailbox.destroyed = True` under mailbox lock,
  - overwrites message contents and clears message list under lock.

Result: mailbox destroy semantics are enforced even for stale in-memory references, matching the original safety comment intent.

### 2) Compose route reliability / non-JS behavior

Updated `http_mail_routes.py`:

- Added shared helper `_send_to_mailbox(...)` to centralize send-path validation and sanitization.
- Added new route:
  - `POST /<path>/mail/send`
  - Accepts mailbox address from:
    - JSON field `address`, or
    - form field `_address_override`
- Existing `POST /<path>/mail/<address>/send` route remains supported.

Updated `templates/http_mail.html`:

- Compose form now stays valid with and without JavaScript:
  - default action points to `/mail/send`,
  - JS listener updates action to `/mail/<address>/send` as user types,
  - fallback route still succeeds if JS is disabled.

## Tests

Updated `tests/test_http_mail.py` with new coverage:

- fallback route success: `POST /mail/send` with form address,
- fallback route validation when address is missing,
- destroyed mailbox behavior:
  - add-message rejected after destroy,
  - `message_count()` is zero when destroyed,
  - inbox read returns denied when destroyed.

## Repository cleanup

Removed stale/generated files:

- Generated sqlite/index artifacts (`.bish-index`, `.bish.sqlite`) across repo directories.
- Redundant duplicate entrypoint: `runserver_refactored.py` (identical to `runserver.py`).
- One-off CI debug scripts no longer referenced:
  - `test-ci-fix.js`
  - `test-server.js`
  - `test_fix.sh`

Documentation updated:

- `docs/development/DEVELOPMENT.md` no longer lists deleted duplicate entrypoint.
- `docs/README.md` quick-start no longer marked TODO.
- `docs/implementation/CHANGELOG.md` updated in `Unreleased` with feature and cleanup notes.

## Notes

- HTTP mail remains intentionally in-memory only.
- Existing route behavior for normal send/inbox/delete/destroy is preserved.
