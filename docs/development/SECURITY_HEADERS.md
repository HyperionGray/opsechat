# Security Headers and CSP Modes

This document describes how response security headers are configured in OpSecChat.

## Overview

Security headers are configured in `security_headers.py` and registered from
`app_factory.py`. All responses include:

- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Server` and `Date` values set to empty strings

## CSP mode configuration

Use `OPSECHAT_CSP_MODE` to control CSP behavior:

- `auto` (default): scans templates and chooses the safest compatible policy
- `strict`: blocks inline scripts and inline styles
- `compatible`: allows inline scripts and inline styles for legacy templates

Example:

```bash
OPSECHAT_CSP_MODE=strict python runserver.py
```

## Why auto mode exists

Several existing templates currently use inline `<script>` tags and inline style
attributes. In `auto` mode, OpSecChat detects those patterns and uses
`compatible` policy to avoid breaking existing pages.

## Hardening path to strict mode

To run safely in `strict` mode:

1. Move inline JavaScript into static files.
2. Replace inline style attributes with CSS classes in static stylesheets.
3. Remove inline event handlers (for example, `onclick`) and attach events in
   JavaScript modules.
4. Start with `OPSECHAT_CSP_MODE=strict` in staging and verify all pages.
