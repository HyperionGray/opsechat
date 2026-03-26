# HTTP Mail Hardening and No-JS Completion (2026-03-26)

## Summary

This update completes unfinished HTTP Mail behavior and hardens mailbox lifecycle handling:

- Added first-class no-JavaScript form routes for creating mailboxes and opening inboxes.
- Added a robust form fallback send route (`/<path>/mail/send`) so compose works without client-side URL rewriting.
- Hardened mailbox destruction semantics with an explicit mailbox tombstone (`destroyed`) checked by writers.
- Removed stale/stub-like checklist comments in active code paths after implementing the behavior.
- Added tests to cover the new no-JS and tombstone behavior.

## Why this change

Recent development added email-over-HTTP as an in-memory alternative to SMTP/IMAP flows. There were two practical gaps:

1. Compose fallback depended on JavaScript mutating the form action.
2. Mailbox destroy flow had follow-up checklist items indicating incomplete writer-guard behavior.

This patch resolves both while preserving default-deny inbox reads and in-memory-only storage guarantees.

## Behavior changes

### New no-JS routes

- `POST /<path>/mail/create`
  - Creates a mailbox and renders address/read key directly in HTML.
- `GET /<path>/mail/inbox`
  - Accepts `_read_address` and `_read_key`, then redirects to canonical inbox URL.
- `POST /<path>/mail/send`
  - Accepts `_address_override` and message fields from HTML form.
  - Works even when JavaScript is disabled.

### Mailbox destruction hardening

- `HttpMailbox` now has `destroyed: bool`.
- `HttpMailbox.add_message(...)` returns `None` when mailbox is destroyed.
- `HttpMailStorage.delete_mailbox(...)`:
  - removes mailbox from global map under storage lock,
  - acquires mailbox lock,
  - sets `destroyed = True`,
  - overwrites and clears messages.

This blocks late writers that hold stale mailbox references after deletion starts.

## Tests

Added/updated tests in `tests/test_http_mail.py`:

- no-JS send fallback route behavior
- no-JS mailbox creation route behavior
- no-JS inbox-open redirect behavior
- no-JS inbox-open validation errors
- write rejection on destroyed mailbox

Validation run:

- `python3 -m pytest tests/test_http_mail.py tests/test_security_headers.py -q`
- Result: `60 passed`

## Repository cleanup in this iteration

Removed stale or temporary tracked artifacts:

- `.bish-index`
- `.bish.sqlite`
- `test-ci-fix.js`
- `test-server.js`
- `test_fix.sh`

Also removed stale TODO wording from docs index:

- `docs/README.md` quick start link text no longer marked TODO.
