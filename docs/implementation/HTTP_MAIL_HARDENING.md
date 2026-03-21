# HTTP Mail Hardening Notes

## Summary

This update hardens the HTTP mail subsystem used by `/mail/*` routes:

- Added explicit mailbox destruction state to prevent writes after teardown.
- Added a no-JavaScript compose endpoint (`POST /<path>/mail/send`) so form submits work without client-side action rewriting.
- Improved error behavior for stale mailbox references (returns `410 Gone` instead of silently accepting writes).
- Expanded test coverage for destruction safety and no-JS send flow.

## Why this was needed

The HTTP mail implementation previously removed a mailbox from global storage but did not explicitly block in-flight writers that still held a mailbox reference. In addition, the no-JS compose form posted to `/mail/send`, but only `/mail/<address>/send` existed.

## Behavior changes

### Mailbox lifecycle

- `HttpMailbox` now tracks `destroyed` state.
- `HttpMailbox.add_message(...)` raises `RuntimeError` when called after mailbox destruction.
- `HttpMailStorage.delete_mailbox(...)` now calls `mailbox.destroy()` to atomically mark destroyed and wipe message contents.

### Routing

- New route: `POST /<path>/mail/send`
  - Reads address from form field `_address_override` (or JSON `address`).
  - Reuses the same send logic as `POST /<path>/mail/<address>/send`.
  - Returns 400 if address is missing.

## Tests added

- `test_destroyed_mailbox_rejects_new_messages`
- `test_send_message_form_route_without_js`
- `test_send_message_form_route_missing_address_fails`

