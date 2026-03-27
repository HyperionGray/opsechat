# HTTP Mail Improvements (2026-03-27)

## Summary

This update completes an unfinished HTTP Mail path and hardens mailbox lifecycle behavior.

## What changed

### 1) No-JavaScript compose flow now works

Previously, the compose form in `templates/http_mail.html` posted to:

- `POST /{path}/mail/send`

But only this endpoint existed:

- `POST /{path}/mail/{address}/send`

That meant non-JS users could not send mail unless client-side JavaScript rewrote the form action at runtime.

Implemented:

- New route: `POST /{path}/mail/send`
  - Reads `_address_override` from form data
  - Validates mailbox address and body
  - Uses existing sanitize/length logic
  - Renders success/error back on `http_mail.html`

Result: compose works with and without JavaScript.

### 2) Mailbox destroy/send race hardening

`HttpMailbox` now tracks a `destroyed` state and `add_message()` refuses writes after destroy.

Implemented:

- `HttpMailbox.destroyed` flag
- `HttpMailbox.add_message(...) -> Optional[str]`
  - Returns `None` if mailbox is destroyed
- Route handlers return `410 Gone` when a destroyed mailbox is targeted during a send race

This closes a lifecycle gap where a mailbox object captured before deletion could still accept late writes.

### 3) Test coverage updates

Added tests for:

- Form fallback send endpoint (`POST /mail/send`)
- Missing recipient address handling (400)
- Unknown recipient mailbox handling (404)
- Destroyed mailbox rejecting writes

## Files touched

- `http_mail_system.py`
- `http_mail_routes.py`
- `templates/http_mail.html`
- `tests/test_http_mail.py`

## Behavior notes

- JSON clients still use `POST /mail/{address}/send` as before.
- Non-JS users can now use the compose form directly.
- Security model remains default-deny for inbox reads (read key required).
