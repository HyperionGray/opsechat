# HTTP Mail Hardening and Cleanup (2026-03-23)

## Summary

This update completes unfinished HTTP Mail destruction follow-ups, adds a
non-JavaScript compose fallback endpoint, fixes an email route session bug,
and removes stale root-level debug scripts.

## Feature Additions

### 1) Generic compose endpoint

Added:

- `POST /<path>/mail/send`

This endpoint accepts the mailbox address from request data:

- JSON: `{"address": "...", "subject": "...", "body": "...", "sender": "..."}`
- Form: `_address_override=<address>`

The existing address-scoped endpoint remains supported:

- `POST /<path>/mail/<address>/send`

### 2) Address validation

Mailbox addresses are now validated as 12-character base64url tokens before
processing send requests. Invalid addresses return HTTP 400.

## Security/Correctness Hardening

### Destroyed mailbox write-guard

`HttpMailbox` now tracks a `destroyed` state. Once a mailbox is destroyed:

- future `add_message(...)` calls are rejected (`None` return)
- message count reports `0`
- message reads/deletes via stale in-memory references are denied/safe

`HttpMailStorage.delete_mailbox(...)` now:

1. removes mailbox from global mapping under storage lock
2. sets `mailbox.destroyed = True` under mailbox lock
3. overwrites and clears all messages under mailbox lock

This closes the unfinished race-safety checklist around mailbox destruction.

### Email view session helper fix

`email_routes.py` now defines and uses `_ensure_session()` inside
`register_email_routes(...)`, preventing no-session `email_view` requests from
hitting an undefined helper path.

## Repository Cleanup

Removed unreferenced root-level ad-hoc debug scripts:

- `test-ci-fix.js`
- `test-server.js`
- `test_fix.sh`
- `test_mock_server.py`

## Tests Added/Updated

In `tests/test_http_mail.py`:

- generic form send via `/<path>/mail/send`
- generic JSON send via `/<path>/mail/send`
- invalid generic address returns 400
- destroyed mailbox rejects late writes
- no-session email view path returns 404 (regression test)
