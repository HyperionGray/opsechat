# Domain Rotation Lifecycle Update

## Summary

This update completes unfinished domain-rotation integration and adds safer state handling for long-running burner-domain workflows.

## What Changed

### 1. Completed domain manager integration points

`DomainRotationManager` now exposes:

- `configure(api_key, secret_key, monthly_budget, provider="porkbun")`
- `get_config()`

These methods were referenced by existing app code paths but were not implemented.

### 2. Added robust state persistence primitives

`DomainRotationManager` now supports:

- `export_state()` for JSON-safe state snapshots
- `import_state()` for restoring state (including legacy config compatibility)
- datetime parsing/serialization for `purchased_at` and `expires_at`

This fixes the previous CLI persistence issue where datetime values could not be serialized reliably.

### 3. Added monthly budget lifecycle handling

Budget tracking now includes cycle awareness:

- automatic monthly reset when cycle changes (`YYYY-MM`, UTC)
- cycle included in `get_budget_status()`
- manual reset via `reset_budget()`

### 4. Added domain lifecycle controls

`DomainRotationManager` now supports:

- `set_active_domain(domain)`
- `remove_domain(domain)`
- `remove_expired_domains()`

These are used by new CLI commands for practical maintenance.

### 5. Expanded CLI capabilities

`domain_rotation_cli.py` now includes:

- safer state handling with manager import/export
- backward-compatible loading for old config layouts
- `activate <domain>` command
- `prune-expired` command
- `reset-budget` command
- non-interactive status/list behavior without requiring API credentials

## New CLI Examples

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py list
python domain_rotation_cli.py activate example.xyz
python domain_rotation_cli.py prune-expired
python domain_rotation_cli.py reset-budget
```

## Test Coverage Added

- Extended `tests/test_domain_manager.py` with:
  - configure flow test
  - monthly reset behavior test
  - export/import round-trip test
  - active-domain validation test
  - expired-domain cleanup test
- Added `tests/test_domain_rotation_cli.py` for CLI persistence behavior.
