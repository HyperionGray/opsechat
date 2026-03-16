# Email Delivery and Burner Flow Completion

## Summary

This update completes previously unfinished email runtime behavior by connecting the UI routes to the real transport/domain managers and by fixing burner stats/cleanup gaps.

## What is now implemented

### 1) Real compose delivery flow (`/<path>/email/compose`)

- Standard mode and raw mode are both processed server-side.
- When SMTP is configured and `send_via_smtp=true`, compose attempts real SMTP delivery.
- If SMTP send fails, the message is still preserved in the local inbox and users get a clear failure notice.
- If SMTP is not requested, compose stores locally and confirms local-only save.
- Send-rate limits are enforced and shown to users.

### 2) Burner management behavior (`/<path>/email/burner*`)

- Burner page now supports:
  - `POST action=generate`
  - `POST action=rotate`
  - `POST /email/burner/expire/<email>`
- Added `/email/burner/list` endpoint used by template auto-refresh.
- Existing `/email/burner/list.json` now has working stats data from `get_user_stats`.

### 3) Config page runtime wiring (`/<path>/email/config`)

- SMTP configuration form now calls `transport_manager.configure_smtp(...)`.
- IMAP configuration form now calls `transport_manager.configure_imap(...)`.
- Domain API form now configures Porkbun client + monthly budget.
- Config page now receives expected template data:
  - `config_status`
  - `budget_status`
  - `active_domain`
  - status messages

### 4) IMAP fetch and domain rotate actions

- Added `POST /email/receive` to import messages from configured IMAP.
- Added `POST /email/domain/rotate` to rotate to a newly purchased domain and update burner domain.

## Reliability fixes

- Fixed expired burner cleanup so expired entries are also removed from user burner mappings correctly.
- Added `BurnerEmailManager.get_user_stats(user_id)` for API/template consumers.

## Cleanup included

- `runserver_refactored.py` is now a compatibility wrapper around `runserver.py` instead of a full duplicate copy.
