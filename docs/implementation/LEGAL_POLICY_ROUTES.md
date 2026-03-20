# Legal Policy Routes Implementation

**Date:** 2026-03-20  
**Version:** 0.8.0-alpha

## Summary

Implemented first-class legal policy endpoints in the Flask application:

- `GET /terms`
- `GET /privacy`
- `GET /aup`

These routes provide a stable URL surface for policy linking and future signup/legal acceptance flows.

## What Changed

### Backend

- Added `legal_routes.py` with `register_legal_routes(app)`.
- Added markdown-backed policy loading from `docs/legal/*.md`.
- Registered legal routes in `app_factory.py`.

### UI

- Added reusable template: `templates/legal_policy.html`.
- Added stylesheet: `static/legal_policy.css`.
- Added legal links in simple chat pages:
  - `templates/simple_chat_index.html`
  - `templates/simple_chat_room.html`
  - `templates/simple_chat_error.html`

### Documentation

- Added missing policy document: `docs/legal/PRIVACY_POLICY.md`.
- Updated docs index to include Privacy Policy and this implementation note.

### Tests

- Added `tests/test_legal_pages.py` to validate:
  - Route availability
  - Key content presence
  - Cross-link visibility between legal pages

## Notes

- Policy files remain draft documents pending legal counsel review.
- This implementation is intentionally read-only and static to minimize risk.
