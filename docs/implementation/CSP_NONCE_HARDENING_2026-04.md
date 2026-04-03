# CSP Nonce Security Hardening (2026-04)

## Summary

This update hardens Content Security Policy (CSP) handling by moving from a
strict "no inline" policy that did not match template reality to a nonce-based
policy that explicitly authorizes vetted inline blocks.

The result is:

- no `unsafe-inline` in `script-src`
- per-request nonce attached to inline script/style blocks that are still needed
- improved CSP baseline directives (`object-src`, `base-uri`, `form-action`)
- reduced risk of accidental client-side script execution

## What Changed

### 1. App-level CSP nonce support (`app_factory.py`)

- Added a `before_request` hook to generate a per-request nonce:
  - `g.csp_nonce = secrets.token_urlsafe(16)`
- Added a context processor to expose `{{ csp_nonce }}` in all templates.
- Updated CSP header generation:
  - `script-src 'self' 'nonce-<value>'`
  - `style-src 'self' 'unsafe-inline' 'nonce-<value>'`
  - `object-src 'none'`
  - `base-uri 'self'`
  - `form-action 'self'`

### 2. Template hardening

Added nonce attributes to inline blocks on templates that use inline JS/CSS and
removed inline JavaScript event handlers where possible.

Key files updated:

- `templates/drop.html`
- `templates/landing_auto.html`
- `templates/http_mail.html`
- `templates/email_compose.html`
- `templates/reviews.html`
- `templates/email_inbox.html`
- `templates/email_burner.html`
- `templates/email_spoof_test.html`
- `templates/email_edit.html`
- `templates/email_view.html`

Representative behavior changes:

- `onclick=` and `onchange=` handlers replaced with `addEventListener(...)`.
- delete/destroy confirmations moved from inline handlers to JS listeners.
- tab switching and compose-mode toggles moved to listener-based logic.

### 3. Test updates

Updated tests to validate nonce-based CSP semantics and header consistency:

- `tests/test_security_headers.py`
- `tests/test_rate_limit_and_health.py`

Added assertions for:

- no `unsafe-inline` in `script-src`
- nonce presence in CSP
- nonce-marked script tags in rendered HTML
- expanded CSP directives on `/health`

## Validation

Targeted test run:

```bash
python3 -m pytest -q tests/test_security_headers.py tests/test_rate_limit_and_health.py tests/test_simple_chat_routes.py
```

Result:

- `66 passed`

## Repository Cleanup Included

Removed stale artifacts:

- `Dockerfile~HEAD`
- `docker-compose.yml~HEAD`
- `templates/email_burner_old.html`

These files were unreferenced and duplicated functionality already represented
in active files.
