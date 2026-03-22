# HTTP Mail Hardening and Fallback Compose

## Summary

This update hardens the Email-over-HTTP subsystem and closes unfinished implementation checklist items by:

1. Rejecting writes to destroyed mailboxes.
2. Adding a no-JavaScript compose fallback endpoint.
3. Returning user-friendly HTML errors for form-based send failures.

## What Changed

### 1) Destroyed mailbox write guard

File: `http_mail_system.py`

- `HttpMailbox` now tracks a `destroyed` state.
- `add_message(...)` returns `None` when a mailbox has been destroyed.
- `HttpMailStorage.delete_mailbox(...)` now always:
  - removes mailbox from global storage under storage lock,
  - overwrites and clears messages under mailbox lock,
  - marks the mailbox as destroyed.

This prevents stale mailbox object references from accepting new writes after deletion.

### 2) Non-JS compose fallback route

File: `http_mail_routes.py`

- Added `POST /<path>/mail/send`
- Reads `_address_override` from form data and forwards to the primary send handler.
- Enables the HTML compose form to function even when JavaScript is unavailable.

### 3) Better HTML error handling for send

File: `http_mail_routes.py`

For non-JSON requests to send endpoints:

- missing mailbox now renders an HTML error page with `404`
- message required validation still returns HTML `400`
- destroyed/unavailable mailbox returns HTML `410`

## Tests Added

File: `tests/test_http_mail.py`

- mailbox references reject writes after deletion
- destroyed mailbox rejects new messages
- fallback compose route works end-to-end
- fallback compose route validates missing address

## Operational Impact

- No API contract break for existing JSON clients.
- Improved resilience against race-y stale references.
- Better accessibility and reliability for form-based usage.
