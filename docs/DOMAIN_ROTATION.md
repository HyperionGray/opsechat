# Domain Rotation

This document describes the current domain rotation implementation used by
OpSecChat burner email workflows.

## Current Components

- `domain_manager.py`
  - `PorkbunAPIClient`: registrar API adapter
  - `DomainRotationManager`: budget checks, domain discovery, purchasing,
    active-domain tracking
- `domain_rotation_cli.py`
  - CLI for configuration, searching, rotating, status, and listing

## Supported Flow

1. Configure registrar credentials and budget.
2. Find a cheap available domain (default threshold: `$5`).
3. Purchase only if budget allows.
4. Mark purchased domain as active.
5. Persist runtime state (CLI mode).

## Runtime and Persistence

`DomainRotationManager` now exposes state helpers:

- `export_state()` returns JSON-safe state.
- `load_state(state)` restores state, including ISO timestamp parsing.
- `get_config()` exposes safe runtime status for UI/API surfaces.
- `configure(...)` sets API credentials and monthly budget.
- `rotate_domain_with_details()` returns structured JSON-friendly results.

In CLI mode, state is persisted in:

- `~/.opsechat/domain_config.json`
- file mode `0600`
- legacy top-level state keys remain supported for compatibility

## CLI Quick Reference

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

For setup and registrar details, see:

- `docs/setup/DOMAIN_API_SETUP.md`
- `docs/setup/DOMAIN_REGISTRAR_API.md`
