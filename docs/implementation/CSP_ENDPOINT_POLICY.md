# CSP Endpoint Policy

## Purpose

The app now uses endpoint-aware Content Security Policy (CSP) handling in `app_factory.py` to finish the security hardening work without breaking legacy pages that still contain inline JavaScript/style attributes.

## Behavior

Two CSP policies are applied:

- **Strict policy (default)** for all non-legacy endpoints.
  - `script-src 'self'`
  - `style-src 'self'`
  - no `'unsafe-inline'`
- **Legacy compatibility policy** for selected HTML endpoints that still rely on inline script/style/event handlers.
  - `script-src 'self' 'unsafe-inline'`
  - `style-src 'self' 'unsafe-inline'`

Selection logic:

1. If response MIME type is not `text/html`, strict policy is used.
2. If response is HTML and endpoint is in the legacy allowlist, compatibility policy is used.
3. Otherwise strict policy is used.

## Why this approach

- Keeps strict defaults for new/minimal routes (`/`, `/health`, `/chat`, and JSON endpoints).
- Avoids regressions on legacy templates that currently depend on inline handlers.
- Provides a clean migration path: remove inline script/style from a template, then remove its endpoint from the allowlist.

## Migration guidance

For each legacy endpoint:

1. Move inline scripts into `/static/*.js`.
2. Replace inline style attributes with CSS classes in `/static/*.css`.
3. Remove `onclick` / other inline handlers in favor of event listeners.
4. Remove endpoint from `LEGACY_HTML_ENDPOINTS`.
5. Add/adjust tests to assert strict CSP for that endpoint.

## Tests

`tests/test_security_headers.py` includes:

- strict CSP assertion (no `'unsafe-inline'`) for strict endpoints
- compatibility CSP assertion for a known legacy HTML endpoint
