# Security Header Policy

This document describes the response-header baseline enforced by `app_factory.py`.

## Goals

- Keep API/JSON endpoints on a strict default-deny CSP profile.
- Maintain compatibility for existing HTML templates while preserving strong framing/object restrictions.
- Provide a migration path away from inline handlers and inline styles.

## Headers Applied to All Responses

- `Content-Security-Policy` (profile depends on response MIME type)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Server: ""`
- `Date: ""` (intentionally blanked for this deployment model)

## CSP Profiles

### 1) HTML Compatibility Profile (`text/html`, `application/xhtml+xml`)

Used for rendered templates where legacy inline script/style patterns still exist.

Policy shape:

- `default-src 'self'`
- `script-src 'self' 'nonce-<per-request>' 'unsafe-inline'`
- `style-src 'self' 'nonce-<per-request>' 'unsafe-inline'`
- `img-src 'self' data:`
- `font-src 'self'`
- `connect-src 'self'`
- `object-src 'none'`
- `base-uri 'self'`
- `form-action 'self'`
- `frame-ancestors 'none'`

### 2) API/Non-HTML Strict Profile

Used for JSON and other non-HTML responses (for example `/health`).

Policy shape:

- `default-src 'none'`
- `script-src 'none'`
- `style-src 'none'`
- `img-src 'none'`
- `font-src 'none'`
- `connect-src 'self'`
- `object-src 'none'`
- `base-uri 'none'`
- `form-action 'none'`
- `frame-ancestors 'none'`

## Nonce Support

Each request gets a generated CSP nonce and templates can use:

- `{{ csp_nonce }}` in `<script nonce="{{ csp_nonce }}">...`
- `{{ csp_nonce }}` in `<style nonce="{{ csp_nonce }}">...`

This allows incremental hardening while keeping existing pages working.

## Migration Plan

To fully remove `'unsafe-inline'` for HTML responses:

1. Move inline event handlers (e.g., `onclick=...`) into static JavaScript files.
2. Move inline styles to stylesheet classes.
3. Keep only nonce-based inline blocks where unavoidable.
4. Remove `'unsafe-inline'` from `script-src` and `style-src`.

