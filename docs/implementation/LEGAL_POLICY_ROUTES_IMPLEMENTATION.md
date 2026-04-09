# Legal Policy Routes Implementation

## Summary

Implemented first-class legal policy pages in the web app and linked them from user-facing chat templates.

This work adds:

- `GET /terms` -> Terms of Service page
- `GET /privacy` -> Privacy Policy page
- `GET /aup` -> Acceptable Use Policy page

The pages are rendered from canonical markdown documents in `docs/legal/`.

## What Changed

### 1) New legal routes module

- Added `legal_routes.py`
- Added `register_legal_routes(app)` and registered it in `app_factory.py`
- Added a constrained markdown-to-HTML renderer for policy docs
- Added link rewriting for internal policy references:
  - `TERMS_OF_SERVICE.md` -> `/terms`
  - `PRIVACY_POLICY.md` -> `/privacy`
  - `ACCEPTABLE_USE_POLICY.md` -> `/aup`

### 2) New policy templates and styling

- Added `templates/legal_policy.html`
- Added `static/legal-policy.css`

### 3) New Privacy Policy document

- Added `docs/legal/PRIVACY_POLICY.md`

### 4) Added legal links in active user templates

Updated templates to expose Terms/Privacy/AUP links:

- `templates/simple_chat_index.html`
- `templates/simple_chat_room.html`
- `templates/simple_chat_error.html`
- `templates/landing.html`
- `templates/drop.noscript.html`
- `templates/drop.html`

### 5) Tests

- Added `tests/test_legal_routes.py`
  - Validates `/terms`, `/privacy`, and `/aup` return 200
  - Validates policy navigation links on policy pages
  - Validates legal links are present on `/chat`

## Validation

Executed:

- `python3 tests/manual/pf_tasks_check.py` -> pass
- `python3 -m pytest tests/test_legal_routes.py tests/test_security_headers.py tests/test_simple_chat_routes.py -q` -> pass (55 tests)

## Cleanup Included

Removed stale tracked backup artifacts from repo root:

- `Dockerfile~HEAD`
- `docker-compose.yml~HEAD`
