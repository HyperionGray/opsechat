# HTTP Mail Send Fallback and Destroy Guards

Date: 2026-03-21

## Summary

This update extends the email-over-HTTP work with two practical improvements:

1. A no-JavaScript compose fallback endpoint:
   - `POST /<path>/mail/send`
   - Accepts mailbox address from request payload (`_address_override` in form, `address` in JSON).
2. Mailbox destruction hardening:
   - `HttpMailbox` now tracks a `destroyed` flag under lock.
   - Stale mailbox references can no longer accept writes after mailbox destruction.

These changes improve reliability for scripted/form clients and close a race window during mailbox deletion.

## Why this was needed

- The compose form posted to `/mail/send`, but only `/mail/<address>/send` was implemented.
- `HttpMailStorage.delete_mailbox` had inline follow-up checklist notes for destroyed-mailbox write protection.

This change completes those unfinished implementation details.

## Technical details

### Route updates

- Added `POST /<path>/mail/send` in `http_mail_routes.py`.
- Introduced shared send logic so both send endpoints validate and sanitize consistently.
- Form clients now receive HTML errors for missing address/mailbox; JSON clients receive JSON errors.

### Mailbox lifecycle updates

- `HttpMailbox` now has `self.destroyed = False`.
- `add_message` raises `RuntimeError` if called after destruction.
- `delete_message` and `get_messages` treat destroyed mailboxes as unavailable/empty.
- `HttpMailStorage.delete_mailbox` marks mailbox as destroyed while holding the mailbox lock, then scrubs message memory.

## Tests added

In `tests/test_http_mail.py`:

- `test_destroyed_mailbox_rejects_stale_writes`
- `test_send_message_form_with_address_override`
- `test_send_message_form_missing_address_fails`

These tests verify the new behavior for both lifecycle safety and form-based sending.
