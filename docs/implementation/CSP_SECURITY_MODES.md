# CSP Security Modes and Nonce Support

Date: 2026-03-19

## Summary

`app_factory.py` now implements a configurable Content Security Policy (CSP) mode:

- `compat` (default): preserves compatibility with existing templates that still use inline script blocks.
- `strict`: emits a per-request nonce and requires inline scripts to present the matching nonce.

Both modes also set additional hardening directives (`object-src`, `base-uri`, and `form-action`).

## Configuration

Set the environment variable:

```bash
OPSECHAT_CSP_MODE=compat   # default
OPSECHAT_CSP_MODE=strict
```

If an invalid value is provided, the app falls back to `compat`.

## Behavior

### compat mode

- `script-src 'self' 'unsafe-inline'`
- `style-src 'self' 'unsafe-inline'`
- Intended for current templates while migration is still in progress.

### strict mode

- `script-src 'self' 'nonce-<per-request-nonce>'`
- `style-src 'self' 'unsafe-inline'`
- Nonce is generated per request and exposed to templates as `{{ csp_nonce }}`.

## Template usage in strict mode

Use the nonce for inline script tags:

```html
<script nonce="{{ csp_nonce }}">
  // inline script content
</script>
```

## Validation

New tests in `tests/test_rate_limit_and_health.py` verify:

1. default `compat` behavior
2. strict mode nonce in the CSP header
3. template nonce injection matching the header nonce
