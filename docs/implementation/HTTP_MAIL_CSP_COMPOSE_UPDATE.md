# HTTP Mail CSP and Compose Update

## Summary

This update completes two unfinished parts of the HTTP Mail feature:

1. **CSP compatibility for the HTTP Mail UI**
2. **No-JS compose support via a dedicated form endpoint**

The app enforces a strict Content Security Policy (`script-src 'self'; style-src 'self'`), but the HTTP Mail page previously relied on inline `<style>`, inline `<script>`, and inline event handlers. That prevented parts of the UI from working under production security headers.

## What changed

### 1) CSP-compliant static assets

- Moved HTTP Mail inline CSS from `templates/http_mail.html` to:
  - `static/http_mail.css`
- Moved HTTP Mail inline JS from `templates/http_mail.html` to:
  - `static/http_mail.js`
- Replaced inline `onclick` handlers with `addEventListener(...)` wiring in `http_mail.js`.
- Replaced inline `style=""` usage in the template with reusable CSS classes.

Result: HTTP Mail now works with strict CSP without relaxing policy.

### 2) Added no-JS compose endpoint

- Added route:
  - `POST /<path>/mail/send`
- This route accepts `_address_override` (form) or `address` (JSON), validates it, and sends the message using shared send logic.
- Existing route remains:
  - `POST /<path>/mail/<address>/send`

Result: users can submit the compose form without JavaScript route rewriting.

### 3) Route cleanup and response consistency

In `http_mail_routes.py`:

- Added shared helpers for:
  - template rendering context
  - JSON response detection
  - send payload parsing
  - mailbox address validation
- Reduced duplicated send/inbox rendering logic.

### 4) Additional cleanup

In `email_routes.py`:

- Added missing `_ensure_session()` helper used by `email_view`.
- Removed duplicate `get_email(...)` call in `email_view`.

## Tests added/updated

Updated `tests/test_http_mail.py` with:

- `test_mail_index_uses_external_assets_for_csp`
- `test_send_message_via_no_js_form_endpoint`
- `test_send_message_via_no_js_form_requires_address`

These tests verify:

- Template uses external static assets and no inline `<style>`/bare `<script>` tags.
- New compose route works for non-JS form submission.
- Address is required for the no-JS compose endpoint.

## Operational impact

- No config or migration changes required.
- Existing HTTP Mail API paths continue to work.
- Security posture is improved by aligning feature behavior with current CSP policy.
