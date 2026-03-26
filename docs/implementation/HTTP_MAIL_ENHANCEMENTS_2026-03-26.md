# HTTP Mail Enhancements - 2026-03-26

## Summary

This update continues the recent email-over-HTTP work by finishing a few incomplete integration points and tightening security/behavior.

## What was implemented

### 1. Generic send endpoint for compose form and API clients

- Added route: `POST /<path>/mail/send`
- Supports both JSON and form payloads:
  - `address` (JSON) or `_address_override` / `address` (form)
  - `subject`, `body`, `sender`
- This fixes the compose UI flow, which posts to `/mail/send`.

### 2. Stronger mailbox destroy semantics

- `HttpMailbox` now has a `destroyed` flag.
- `add_message(...)` now returns `None` if mailbox is destroyed.
- `HttpMailStorage.delete_mailbox(...)` now:
  - validates key,
  - marks mailbox destroyed under lock,
  - removes mailbox from global map,
  - overwrites all message content,
  - clears message list.
- Routes return `410` if a send request races with a destroyed mailbox object reference.

### 3. CSP-compatible HTTP Mail frontend

The app enforces CSP with `script-src 'self'` and `style-src 'self'`, so inline script/style are blocked.

To align HTTP Mail with that policy:

- Moved all inline CSS from template to `static/http_mail.css`.
- Moved all inline JS from template to `static/http_mail.js`.
- Removed inline event handler attributes (e.g. `onclick=...`).
- Added non-inline bootstrap data via `data-*` attributes for script initialization.

### 4. API usability improvement

- `POST /<path>/mail/new` now also returns:
  - `read_url` (`/<path>/mail/<address>/inbox?key=<read_key>`)

## Tests updated

Extended `tests/test_http_mail.py` to cover:

- generic send endpoint via JSON and form,
- address-required validation on generic endpoint,
- new `read_url` response field,
- destroyed mailbox state behavior.

## Files changed

- `http_mail_routes.py`
- `http_mail_system.py`
- `templates/http_mail.html`
- `static/http_mail.css` (new)
- `static/http_mail.js` (new)
- `tests/test_http_mail.py`

