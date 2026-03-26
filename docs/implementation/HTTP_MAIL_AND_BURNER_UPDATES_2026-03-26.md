# HTTP Mail and Burner Updates - 2026-03-26

## Summary

This update continues the email-over-HTTP direction by making compose/send fully functional
without JavaScript and by completing burner stats API wiring that was previously incomplete.
It also includes route/session hardening and cleanup of stale TODO markers in core mail code.

## What Changed

### 1. HTTP Mail no-JS compose flow completed

Previously, the `http_mail.html` compose form defaulted to:

- `POST /{path}/mail/send`

but only this endpoint existed:

- `POST /{path}/mail/{address}/send`

That meant no-JS form submissions failed unless JavaScript rewrote the form action first.

Implemented:

- New route: `POST /<path>/mail/send`
  - Accepts address from form (`_address_override`) or JSON (`address`)
  - Validates required address
  - Reuses shared send logic with the existing address-specific endpoint
- Shared response handling so HTML and JSON callers get consistent errors/success

Result:

- Compose works in both NoScript and JavaScript modes.

### 2. Burner stats endpoint completion

`email_burner/list(.json)` returned `burner_manager.get_user_stats(...)`, but
`BurnerEmailManager` did not implement that method.

Implemented in `email_system.py`:

- `get_user_stats(user_id)` returning:
  - `active_burners`
  - `total_time_remaining_seconds`
  - `max_sends_per_hour`
  - `send_limit` (from existing rate-limit tracking)

Also fixed burner lifecycle consistency:

- `expire_burner(...)` now removes expired addresses from both
  `burner_addresses` and `user_burners`
- `cleanup_expired(...)` now captures `user_id` before deletion to avoid stale list entries

### 3. Email route hardening and cleanup

`email_routes.py` improvements:

- Added shared `_ensure_session()` helper and used it consistently
- Removed duplicate `get_email(...)` call in `email_view`
- Fixed potential runtime path where `_ensure_session()` was referenced but not defined
- Burner page now supplies `active_burners` expected by the template
- Added support for both:
  - `GET /<path>/email/burner/list`
  - `GET /<path>/email/burner/list.json`

### 4. Mailbox destroy semantics completed

`http_mail_system.py` improvements:

- Added mailbox-level `destroyed` flag
- `HttpMailbox.add_message(...)` now refuses writes after destroy
- `delete_mailbox(...)` marks mailbox destroyed while safely clearing/overwriting messages
- Removed stale checklist TODO markers in delete path

### 5. Documentation and index updates

- Updated `docs/user-guide/EMAIL_SYSTEM.md` with a dedicated HTTP Mail section:
  - mailbox model (`address` + `read_key`)
  - endpoint list
  - no-JS/JS behavior
- Added HTTP Mail link to `docs/README.md` user guide section

## Tests Added / Updated

### `tests/test_http_mail.py`

Added coverage for:

- Generic no-JS send route (`POST /mail/send`) with form payload
- Generic send route with JSON payload (`address` in body)
- Required address validation (HTML + JSON)
- Sending to destroyed mailbox returns `404`
- Adding message to destroyed mailbox raises runtime error
- Session initialization path in email view route

### `tests/test_email_system.py`

Added coverage for:

- `BurnerEmailManager.get_user_stats(...)` output shape and values

## Why This Matters

- Restores true progressive enhancement (NoScript behavior works end-to-end)
- Removes hidden runtime errors in burner stats API and email route session handling
- Improves correctness of in-memory burner/mailbox lifecycle state
- Keeps repository cleaner by replacing stale TODO/checklist comments with implemented logic
