# Simple Chat CSP Migration

## Summary

The simple chat frontend was migrated to be compatible with the strict
Content-Security-Policy configured in `app_factory.py`:

- `script-src 'self'`
- `style-src 'self'`

This removes the previous runtime mismatch where simple chat templates used
inline `<script>` and `<style>` blocks, plus inline handlers.

## What Changed

### Template updates

- `templates/simple_chat_index.html`
- `templates/simple_chat_room.html`
- `templates/simple_chat_error.html`

All three templates now:

- load shared CSS from `static/simple_chat.css`
- load page JavaScript from external files
- avoid inline event handlers (for example `onclick`)
- avoid inline `style=` attributes

### New static assets

- `static/simple_chat.css` (shared styling for index/room/error)
- `static/simple_chat_index.js` (room creation UX)
- `static/simple_chat_room.js` (message polling, encryption toggle, warning modal)

### Test coverage

Added CSP-focused regression tests in:

- `tests/test_simple_chat_routes.py`

The tests verify simple chat pages use external assets only and do not re-add
inline script/style/event-handler patterns.

## Cleanup in this change

- Removed unreferenced duplicate file: `tests/mock_server_refactored.py`
- Removed stale implementation checklist comments from `app_factory.py`

## Why this matters

This keeps the simple chat path aligned with the existing security headers
without relaxing CSP and reduces the chance of template regressions.
