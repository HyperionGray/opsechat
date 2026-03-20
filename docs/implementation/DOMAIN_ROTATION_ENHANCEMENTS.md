# Domain Rotation Enhancements (March 2026)

## Summary

This update completes unfinished domain-rotation integration points and adds
reliable state persistence for the CLI workflow.

## What was implemented

1. `DomainRotationManager` now exposes configuration and status APIs:
   - `configure(api_key, secret_key, monthly_budget, provider="porkbun")`
   - `get_config()`
2. Added structured rotation API:
   - `rotate_to_new_domain(max_price=5.0)` returns a dictionary with
     `success`, `domain/cost` on success, and `error` on failure.
3. Added bulk discovery API:
   - `search_cheap_domains(tlds=None, max_price=5.0, limit=5, max_attempts=25)`
4. Improved price parsing:
   - Handles numeric, dollar/euro prefixed, and comma-formatted values.
5. CLI persistence fix:
   - `domain_rotation_cli.py` now serializes `datetime` objects to ISO strings
     before writing JSON config.
   - Datetimes are parsed back during load to keep existing behavior.
6. Email domain rotation route alignment:
   - `email_security_routes.py` now uses structured
     `rotate_to_new_domain()` responses.

## Why this matters

- Prevents runtime crashes when saving domain rotation state.
- Makes web/API integration paths callable instead of partial stubs.
- Provides a stable response contract for UI/API consumers.

## Test coverage added

- Extended `tests/test_domain_manager.py` to cover:
  - manager configuration metadata
  - cheap-domain search list behavior
  - structured rotate success/failure paths
- Added `tests/test_domain_rotation_cli.py` to verify:
  - datetime serialization/deserialization
  - serialized config writes from `save_manager_state`
