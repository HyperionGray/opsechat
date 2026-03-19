# Legal Policy Pages Implementation

**Date:** March 19, 2026  
**Status:** Implemented

## Summary

This change introduces first-class web routes for legal documents and a machine-readable metadata endpoint:

- `/terms`
- `/privacy`
- `/aup`
- `/legal/policies.json`

Path-prefixed variants are also supported for existing random-path deployments:

- `/<path>/terms`
- `/<path>/privacy`
- `/<path>/aup`
- `/<path>/legal/policies.json`

## Why this was added

The production checklist calls for policy display pages and policy version tracking. Previously, legal content existed only as markdown files under `docs/legal/` and was not directly available from the running application.

## Implementation details

1. Added `legal_routes.py` and registered it in `app_factory.py`.
2. Added a reusable `templates/legal_policy.html` view that renders markdown content from `docs/legal/`.
3. Added metadata extraction for:
   - `Version`
   - `Effective Date`
   - `Last Updated`
4. Added `docs/legal/PRIVACY_POLICY.md` with policy metadata and initial policy content.
5. Added legal links to chat UI templates:
   - `templates/simple_chat_index.html`
   - `templates/simple_chat_room.html`

## Security/CSP compatibility update

The existing templates rely on inline scripts and inline styles. The previous CSP setting blocked those features in browsers. The CSP header now explicitly allows inline script/style while keeping same-origin restrictions:

- `script-src 'self' 'unsafe-inline'`
- `style-src 'self' 'unsafe-inline'`

This keeps the current UI functional until templates are migrated to nonce/hash-based CSP.

## Tests

Added `tests/test_legal_routes.py` covering:

- unprefixed legal routes
- path-prefixed legal routes
- policy navigation links and titles
- JSON metadata endpoint shape and values
- CSP header compatibility for current chat templates
