# HTTP Mail Hardening and Compose Route

## Summary

This update extends the recent email-over-HTTP work with:

1. A generic compose endpoint for browser/form workflows.
2. Mailbox-destruction hardening that blocks stale mailbox references from accepting new messages.
3. Route-level refactoring to reduce duplicated rendering logic.

## What Changed

### 1) New generic send endpoint

- Added `POST /<path>/mail/send`.
- Accepts mailbox address from:
  - form field `_address_override` (primary), or `address`
  - JSON field `address`
- Keeps existing `POST /<path>/mail/<address>/send` endpoint unchanged.

This aligns with the existing compose UI form action and improves non-JavaScript compatibility.

### 2) Destroyed mailbox write-guard

- `HttpMailbox` now has explicit `destroyed` state.
- `HttpMailbox.add_message(...)` returns `None` when mailbox is destroyed.
- `HttpMailStorage.delete_mailbox(...)` marks mailbox as destroyed while scrubbing in-memory message content.

This closes the stale-reference window where a caller holding an old mailbox object could append messages after mailbox deletion.

### 3) Cleanup/refactor

- Consolidated repeated HTTP mail template rendering into a helper function in `http_mail_routes.py`.
- Removed stale checklist wording in mailbox deletion docs (the implementation is now complete).
- Removed an unused compose action helper function in `templates/http_mail.html`.

## Test Coverage Added

`tests/test_http_mail.py` now includes:

- generic send route (JSON): `POST /mail/send`
- generic send route (form): `POST /mail/send`
- destroyed mailbox rejects stale sends
- deleted mailbox object marked as destroyed

## Notes

- API behavior for existing routes remains backwards compatible.
- New generic route is additive and intended as a UX/compatibility improvement.
