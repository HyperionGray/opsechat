# CSP Nonce Hardening and Repository Cleanup

## Date
2026-04-04

## Summary
This update finishes a previously incomplete security-hardening path around Content Security Policy (CSP) while preserving current UI behavior.

It also removes stale backup and helper files to keep the repository cleaner and easier to navigate.

## Security Changes

### 1) Added per-request CSP nonce generation
- File: `app_factory.py`
- Added a `before_request` hook to generate a unique nonce per request.
- Added a `context_processor` to expose `csp_nonce` to templates.

### 2) Tightened CSP script policy
- File: `app_factory.py`
- CSP now uses:
  - `script-src 'self' 'nonce-<value>'`
  - `script-src-attr 'none'`
  - `object-src 'none'`
  - `base-uri 'self'`
  - `form-action 'self'`
  - existing defense headers remain (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`)

### 3) Updated templates to use script nonces
- Added `nonce="{{ csp_nonce }}"` on inline and external `<script>` tags across active templates.
- Removed inline event handlers from active templates and replaced them with JS event listeners where needed.
- Kept `style-src 'unsafe-inline'` for now because many legacy templates still use inline style attributes.

## Behavior Compatibility Notes
- Script execution now requires a valid nonce or external same-origin script.
- Inline script attributes (such as `onclick`) are blocked by CSP and were removed from active templates.
- No change to intended user flows; only event binding mechanism changed.

## Tests Updated
- `tests/test_security_headers.py`
  - Validates script CSP is strict (no unsafe-inline for scripts)
  - Validates `script-src-attr 'none'`
- `tests/test_rate_limit_and_health.py`
  - Validates key CSP directives on `/health`

## Repository Cleanup
Removed stale/stray files:
- `docker-compose.yml~HEAD`
- `Dockerfile~HEAD`
- `test-ci-fix.js`
- `test-server.js`
- `templates/email_burner_old.html` (unreferenced legacy template)

## Follow-Up (optional)
- Migrate inline CSS usage in templates to class-based stylesheets so `style-src` can eventually drop `'unsafe-inline'`.
