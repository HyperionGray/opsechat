# Policy Routes Implementation

**Date:** March 20, 2026  
**Status:** Implemented

## Summary

Implemented legal policy display routes in the Flask app:

- `GET /terms` -> Terms of Service
- `GET /privacy` -> Privacy Policy
- `GET /aup` -> Acceptable Use Policy

These pages are rendered directly from markdown sources in `docs/legal/` so policy text is maintained in one place.

## Files Added

- `legal_routes.py` - Route registration and policy file loading
- `templates/legal_policy.html` - Shared policy page template
- `docs/legal/PRIVACY_POLICY.md` - New privacy policy document
- `tests/test_policy_routes.py` - Route tests for all policy endpoints

## Files Updated

- `app_factory.py` - Registers legal routes during app creation
- `docs/README.md` - Added links for privacy policy and implementation notes

## Notes

- Policy markdown is loaded from disk via a small cached loader.
- If a policy file is unavailable, the route returns `503` with a short message.
- The template intentionally avoids inline scripts/styles to remain compatible with current CSP settings.
