# HTTP Mail Hardening and Compose Fallback

**Date:** 2026-03-22

## Summary

This update completes unfinished HTTP mail lifecycle work and adds a missing compose feature used by the web UI.

## What was implemented

### 1) Generic compose endpoint

Added:

- `POST /<path>/mail/send`

Behavior:

- Accepts mailbox address in payload (`_address_override` for form submits, `address` for JSON submits).
- Reuses the same validation and sanitization rules as the address-specific route.
- Returns:
  - `400` when mailbox address is missing
  - `404` when mailbox does not exist
  - `200` on success

Why:

- The UI compose form posts to `/mail/send`; this endpoint now exists and works without JavaScript action rewriting.

### 2) Mailbox destruction lifecycle hardening

`HttpMailbox` now tracks `destroyed` state and enforces it under lock:

- `add_message()` raises `RuntimeError` after mailbox destruction
- `delete_message()` and `message_count()` return safe values after destruction
- `get_messages()` returns an empty list for valid keys on destroyed mailboxes

`HttpMailStorage.delete_mailbox()` now:

- removes mailbox from global storage under storage lock
- marks mailbox as destroyed under mailbox lock
- overwrites and clears in-memory messages under mailbox lock

This closes the unfinished lifecycle checklist around blocking writes after destruction.

## Tests added

- Destroyed mailbox rejects future writes.
- Generic form route (`POST /mail/send`) successfully sends mail.
- Generic form route rejects missing mailbox address with `400`.
