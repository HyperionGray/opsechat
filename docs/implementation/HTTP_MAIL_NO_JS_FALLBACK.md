Date: 2026-03-20
Author: Automation Agent

# HTTP Mail No-JS Fallback

## Summary

HTTP Mail now supports direct form-based send and inbox flows that work without JavaScript. This closes a gap where strict CSP settings (`script-src 'self'`) and no-script browser profiles could block core mailbox actions.

## What was added

### New routes

- `POST /<path>/mail/send`
  - Accepts mailbox address from form or JSON body.
  - Supports:
    - `address` (preferred)
    - `_address_override` (legacy compatibility)
  - Reuses the same validation and sanitization logic as address-specific send.

- `GET /<path>/mail/inbox`
  - Accepts:
    - `address`
    - `key`
  - Redirects to canonical inbox route:
    - `GET /<path>/mail/<address>/inbox?key=<read_key>`

### Existing route behavior improvements

- Unified JSON detection for HTTP Mail endpoints:
  - JSON now returns when either request body is JSON or `Accept: application/json` is present.
- Mailbox destruction race hardening:
  - `HttpMailbox.add_message(...)` now refuses writes after mailbox destroy and returns `None`.
  - Send routes return `410 Gone` if a write races with mailbox destruction.

## Template updates

`templates/http_mail.html` now includes:

- Compose form that posts to `/mail/send` with `address` field.
- Read form with `action="/mail/inbox"` and normal submit button.
- Optional "Open Inbox (Live)" button retained for fetch-based UX.

This keeps progressive enhancement:
- No-JS mode works end-to-end.
- JS mode still supports live refresh and dynamic actions.

## Additional cleanup

- Fixed session handling bug in `email_routes.py` (`email_view` now uses a local `_ensure_session` helper).
- Removed duplicate email lookup in `email_view`.
- Removed stale "TODO" marker from `docs/README.md` quick-link text.

