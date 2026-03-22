## HTTP Mail Hardening Update

Date: 2026-03-22  
Area: HTTP Mail (`http_mail_system.py`, `http_mail_routes.py`, `templates/http_mail.html`)  

### Summary

This update continues the recent "email-over-HTTP" direction by hardening mailbox lifecycle behavior and improving no-JavaScript usability.

### What changed

1. Destroyed mailbox safety
   - Added a `destroyed` state to `HttpMailbox`.
   - `add_message` now refuses writes after destruction and returns `None`.
   - `message_count` and message operations now behave safely for destroyed mailboxes.
   - Introduced `HttpMailbox.destroy()` to centralize memory overwrite + teardown.
   - `HttpMailStorage.delete_mailbox()` now uses `mailbox.destroy()` so stale references cannot accept new messages after deletion.

2. No-JS compose fallback route
   - Added `POST /<path>/mail/send`.
   - This route accepts the target mailbox address from form data (`_address_override`) or JSON (`address`).
   - Enables form submit to work even if JavaScript is unavailable or disabled.

3. Mailbox creation response enhancement
   - `POST /<path>/mail/new` now returns `inbox_read_url`, a direct inbox URL that includes the read key query parameter.
   - The HTTP Mail page now displays this URL so users can copy and store it.

4. Route cleanup and consistency
   - Added shared helpers for JSON detection and template rendering context in `http_mail_routes.py`.
   - Added mailbox-address format validation in send handlers.

### Cleanup included

- Removed a stale "TODO-style" quick-link marker in `docs/README.md` ("Quick Start Guide ... (TODO)").
- Removed two unreferenced root-level debug scripts:
  - `test-ci-fix.js`
  - `test-server.js`

### Test coverage added

`tests/test_http_mail.py` now includes:

- protection against writes through stale mailbox references after destroy
- behavior of `HttpMailbox.destroy()` blocking future writes
- `inbox_read_url` response validation
- no-JS form fallback send flow (`POST /<path>/mail/send`)
