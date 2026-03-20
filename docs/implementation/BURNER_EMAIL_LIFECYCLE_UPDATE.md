# Burner Email Lifecycle Update

Date: 2026-03-20

## Summary

This update hardens burner-email state management and removes stale test artifacts.

## What Changed

### 1) Consistent burner expiration state

File: `email_system.py`

`BurnerEmailManager` now keeps `burner_addresses` and `user_burners` in sync across:

- manual expiration (`expire_burner`)
- time-based expiration (`cleanup_expired`)
- reads (`get_user_burners`) via stale-reference self-healing

Previously, `cleanup_expired` removed addresses before looking up ownership, which
could leave stale entries in `user_burners`.

### 2) Completed mock fallback stubs

File: `tests/mock_server.py`

Fallback classes used when `email_system` cannot be imported now implement
minimal in-memory behavior instead of no-op `pass` stubs for:

- inbox creation
- burner generation/rotation
- user lookup
- expiration and cleanup

This improves resilience for isolated test environments and partial import modes.

### 3) Removed stale duplicate test artifact

- Deleted `tests/e2e.spec.js.deprecated`
- Updated `tests/e2e.spec.js` header note accordingly
- Converted `tests/mock_server_refactored.py` into a compatibility shim that
  delegates to `tests/mock_server.py` to avoid code drift

## Tests Added

File: `tests/test_email_system.py`

New tests verify:

- user index cleanup when manually expiring a burner
- user index cleanup when expiring via scheduled cleanup
- self-healing behavior for stale user-index references

## Impact

- Lower risk of stale burner-address references in memory
- Cleaner test tree with reduced duplicate legacy artifacts
- Better behavior in mock/fallback test runtime paths
