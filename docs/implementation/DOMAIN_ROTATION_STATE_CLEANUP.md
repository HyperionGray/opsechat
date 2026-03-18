# Domain Rotation State and Cleanup Improvements

## Summary

This update completes several unfinished pieces in domain rotation behavior and makes the CLI safer to use in long-running workflows.

## What Changed

### 1) Completed manager configuration surface

`DomainRotationManager` now provides:

- `configure(api_key, secret_key, monthly_budget)`  
  Creates and installs a Porkbun client with budget validation.
- `get_config()`  
  Returns non-sensitive configuration/status data for UI and API layers.

This closes the integration gap where routes expected these methods but they were missing.

### 2) Reliable persisted state handling

The manager now supports:

- `export_state()` for JSON-safe persistence
- `import_state()` for restoring prior state

Datetime fields (`purchased_at`, `expires_at`) are now serialized to ISO-8601 strings and parsed back on restore.

This fixes a previous failure mode where saving state could break when raw `datetime` objects were written to JSON.

### 3) Monthly budget lifecycle reset

Spending is now tracked by a calendar-month period (`YYYY-MM`) and automatically resets when the month changes.

This behavior is applied when budget is read and before purchase checks.

### 4) Expired-domain cleanup

The manager now exposes:

- `cleanup_expired_domains()`

Expired domains are pruned from local state, and `active_domain` is corrected if the prior active domain was removed.

### 5) New CLI command: `cleanup`

`domain_rotation_cli.py` now supports:

```bash
python domain_rotation_cli.py cleanup
```

This removes expired domains from local state and persists the updated state.

## Updated CLI State Flow

- `get_manager()` now restores manager state with `import_state()`
- `save_manager_state()` now persists with `export_state()`
- `list` output now safely formats datetime fields, including legacy string values

## Test Coverage Added

`tests/test_domain_manager.py` includes new tests for:

- manager configuration (`configure` + `get_config`)
- datetime-safe export/import round-trip
- expired domain cleanup behavior
- monthly spending reset behavior
