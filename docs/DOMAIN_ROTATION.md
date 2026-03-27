# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows. The current implementation focuses on Porkbun and includes:

- provider-aware domain manager (`DomainRotationManager`)
- budget enforcement and spending tracking
- web route integration (`/email/config`, `/email/domain/rotate`)
- CLI workflow (`domain_rotation_cli.py`)

## Supported Registrars

Currently available:

- `porkbun` (implemented)

Architecture support exists for multiple providers via `add_api_client()` and `set_active_provider()`. Additional providers can be added by implementing `DomainAPIClient`.

## Configure Domain Rotation

### Web configuration

1. Open `/<secret-path>/email/config`
2. In "Domain API (Porkbun)" fill:
   - API key
   - API secret
   - monthly budget
3. Submit "Configure Domain API"

Route behavior:

- `POST /<path>/email/config` with `action=configure_domain_api` calls `domain_rotation_manager.configure(...)`
- `GET /<path>/email/config` renders masked configuration metadata from `domain_rotation_manager.get_config()`

### CLI configuration

```bash
python domain_rotation_cli.py config
```

The CLI stores credentials in `~/.opsechat/domain_config.json` with mode `0600`.

## Rotation Workflows

### Python API

```python
from domain_manager import domain_rotation_manager

status = domain_rotation_manager.get_budget_status()
print(status)

result = domain_rotation_manager.rotate_to_new_domain(max_price=5.0)
if result["success"]:
    print("Rotated to:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

### Web route

`POST /<path>/email/domain/rotate`:

- purchases a new domain when available and within budget
- returns JSON for API callers
- for browser form submissions, redirects back to `/email/config` with a status message
- on success updates burner email domain via `burner_manager.set_custom_domain(...)`

### CLI commands

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Budget Behavior

- Purchases are rejected if `current_spending + price > monthly_budget`
- `get_budget_status()` returns:
  - `monthly_budget`
  - `current_spending`
  - `remaining`
  - `domains_owned`

## State Persistence (CLI)

`DomainRotationManager` now supports:

- `serialize_state()` for JSON-safe state export
- `load_state()` for restoration (including datetime parsing)

The CLI uses this state to preserve:

- active domain
- owned domain purchase/expiry history
- current spending
- active provider

## Security Notes

- Never commit registrar credentials.
- Keep API keys scoped and rotated.
- Prefer low spending caps initially (for example, `$10` monthly) and adjust only after verifying operational behavior.
