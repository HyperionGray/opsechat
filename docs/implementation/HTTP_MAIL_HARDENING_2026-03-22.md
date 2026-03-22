# HTTP Mail Hardening and Cleanup (2026-03-22)

## Summary

This update continues the recent email-over-HTTP work and closes unfinished implementation details in mailbox lifecycle handling, route stability, and CSP compatibility for inline scripts.

## Implemented

### 1) HTTP mailbox destruction safety completed

`http_mail_system.py` now enforces a concrete destroyed-state contract:

- `HttpMailbox.destroyed` flag is explicit and initialized.
- `add_message()` rejects writes after destruction.
- `get_messages()` and `delete_message()` reject access after destruction.
- `delete_mailbox()` now marks the mailbox destroyed under mailbox lock before scrubbing message memory.

This completes the prior in-code checklist around concurrent destroy/write behavior.

### 2) Read-key rotation feature

New API support for rotating mailbox read credentials without losing messages:

- Storage method: `HttpMailStorage.rotate_mailbox_read_key(address, read_key)`
- Mailbox method: `HttpMailbox.rotate_read_key(current_read_key)`
- Route: `POST /<path>/mail/<address>/rotate-key`

Request body:

- JSON: `{ "read_key": "<current-read-key>" }`
- or form field: `read_key=<current-read-key>`

Response:

- `200` with `{ "success": true, "read_key": "<new-read-key>" }`
- `403` for invalid key or missing mailbox

After rotation, the old key no longer authorizes inbox reads.

### 3) Email route bug fix

`email_routes.py` cleanup:

- Added missing `_ensure_session()` helper used by `email_view`.
- Removed duplicate email lookup in `email_view`.

### 4) CSP nonce support for inline scripts

To keep strict CSP semantics while supporting existing inline script blocks:

- `app_factory.py` now creates a per-request nonce.
- CSP header includes: `script-src 'self' 'nonce-<value>'`.
- Templates with inline scripts now include `nonce="{{ csp_nonce }}"`.

This avoids enabling `unsafe-inline` for scripts.

## Repository cleanup

- Removed stale unreferenced template: `templates/email_burner_old.html`.
- Cleaned docs index entries:
  - Removed obsolete `(TODO)` marker for quick start.
  - Added this implementation note to docs index.

## Tests added/updated

- `tests/test_http_mail.py`
  - Added destroyed mailbox post-delete behavior test.
  - Added read-key rotation endpoint tests.
- `tests/test_security_headers.py`
  - Added CSP nonce presence test.
  - Added nonce/header-to-template matching test.
