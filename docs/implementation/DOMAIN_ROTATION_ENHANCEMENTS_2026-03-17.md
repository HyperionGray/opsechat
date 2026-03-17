# Domain Rotation Enhancements (2026-03-17)

## Summary

This update completes unfinished domain-rotation behavior by adding:

1. Durable manager state import/export for CLI persistence
2. A safe test mode for dry-run domain rotation
3. Multi-client plumbing in the manager (active client selection and registry)
4. Compatibility helper APIs used by existing docs/routes
5. Better price normalization and structured rotate results

## Why this was added

The previous implementation had partially finished behavior:

- CLI state could store datetime values in JSON, then fail when listing domains later.
- Rotation only exposed a string/None path, which made it harder to report failures.
- No built-in dry-run workflow existed for validating rotation without spending money.
- Manager configuration helpers expected by other code paths were missing.

## What changed

### `domain_manager.py`

- Added `DomainRotationManager.export_state()` and `import_state()` for safe serialization.
- Added `set_test_mode()` and test-mode purchase simulation.
- Added `rotate_to_new_domain()` with structured success/error payloads.
- Kept `rotate_domain()` for backward compatibility (still returns active domain string or `None`).
- Added `search_cheap_domains()` for multi-result cheap-domain discovery.
- Added `configure()` and `get_config()` helper methods.
- Added API-client registry support:
  - `set_api_client(...)`
  - `add_api_client(...)`
  - `set_active_client(...)`
- Improved price parsing (`$`, `EUR/GBP symbols`, comma-separated values).

### `domain_rotation_cli.py`

- CLI now reads/writes manager state via the new `state` payload.
- Added legacy-key fallback support for old config files.
- Added `test-rotate` command:
  - Simulates purchase in manager test mode
  - Persists resulting active domain/state
- `search` now uses `search_cheap_domains()` and prints unique results.
- `list` now formats serialized datetime strings safely.

### Tests

Extended `tests/test_domain_manager.py` with coverage for:

- Unique multi-result search behavior
- Test mode avoiding real registrar purchase calls
- Export/import state roundtrip correctness
- Secret masking in config output

## Usage

```bash
# Configure registrar credentials
python domain_rotation_cli.py config

# Dry-run a rotation (no registrar charge)
python domain_rotation_cli.py test-rotate

# Real rotation
python domain_rotation_cli.py rotate

# Inspect persisted state
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

## Cleanup note

As part of this pass, stale one-off helper script `test_fix.sh` was removed from repo root.
