# CSP Nonce Hardening

**Date:** 2026-03-19  
**Author:** Automation Agent

## Summary

Implemented per-request Content Security Policy (CSP) nonces for template script tags.  
This closes the mismatch where templates contained inline `<script>` blocks while CSP
previously allowed only `script-src 'self'`.

## What Changed

### 1) `app_factory.py`

- Added a `before_request` hook that generates a random nonce for each request.
- Added a Jinja context helper `csp_nonce()` so templates can reference the nonce.
- Updated CSP header generation to include:
  - `script-src 'self' 'nonce-<value>'`

### 2) Templates

Added `nonce="{{ csp_nonce() }}"` to every `<script>` tag under `templates/` that lacked one.

Updated files:

- `templates/drop.html`
- `templates/email_burner.html`
- `templates/email_burner_old.html`
- `templates/email_compose.html`
- `templates/email_inbox.html`
- `templates/email_spoof_test.html`
- `templates/landing_auto.html`
- `templates/reviews.html`
- `templates/simple_chat_index.html`
- `templates/simple_chat_room.html`

### 3) Tests

Added `tests/test_csp_nonce.py` to verify:

- CSP header includes a script nonce.
- Rendered HTML script tags receive the matching nonce.
- Nonce value changes across requests.

## Cleanup Included

- Updated `docs/README.md` to remove stale "(TODO)" wording in quick links.
- Added this document to the implementation docs index.

## Notes

- This change focuses on script execution controls.
- Existing inline style attributes are still governed by the `style-src` policy.
