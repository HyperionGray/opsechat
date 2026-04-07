# Domain Rotation Guide

## Overview

OpSecChat includes a production-ready domain rotation manager for burner email
domains. It supports:

- Porkbun API integration
- Budget-aware domain purchasing
- Active domain tracking
- JSON-safe state export/load for CLI persistence

This document reflects the current implementation in:

- `domain_manager.py`
- `domain_rotation_cli.py`
- `email_routes.py` (`/<path>/email/config` and `/<path>/email/domain/rotate`)

## Supported Registrar

Currently supported:

- **Porkbun** (`provider="porkbun"`)

The manager can be extended by implementing `DomainAPIClient` subclasses.

## Configure Domain Rotation (Web UI)

1. Open `http://<host>/<secret-path>/email/config`
2. In **Domain API (Porkbun)**, enter:
   - API key
   - API secret
   - Monthly budget
3. Submit **Configure Domain API**
4. Use **Rotate to New Domain** to buy and activate a new domain

The UI uses:

- `domain_rotation_manager.configure(...)`
- `domain_rotation_manager.get_budget_status()`
- `domain_rotation_manager.get_active_domain()`

## Configure Domain Rotation (CLI)

Run interactive setup:

```bash
python domain_rotation_cli.py config
```

Supported commands:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

CLI state is persisted under:

`~/.opsechat/domain_config.json`

with strict file permissions (`0600`).

## Python API (Current)

### 1) Configure manager

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=20.0,
)
```

### 2) Rotate domain

```python
new_domain = domain_rotation_manager.rotate_domain()
if new_domain:
    print("Active domain:", new_domain)
else:
    print("No eligible domain found or purchase failed")
```

### 3) Inspect status/config

```python
print(domain_rotation_manager.get_budget_status())
print(domain_rotation_manager.get_config())  # API key is masked
```

### 4) Persist/reload state (JSON-safe)

```python
state = domain_rotation_manager.export_state()
# persist `state` as JSON, then later:
domain_rotation_manager.load_state(state)
```

## Budget Behavior

- Purchase is denied if `current_spending + price > monthly_budget`
- Spending and owned domain list are updated only on successful purchase
- The first purchased domain becomes `active_domain`
- `rotate_domain()` sets the newly purchased domain active

## Domain Selection Strategy

The manager currently searches across low-cost TLDs:

- `.xyz`
- `.club`
- `.online`
- `.site`
- `.website`

`find_cheap_available_domain(max_price=..., max_attempts=...)` randomizes
candidate domains and returns the first one meeting availability + budget
constraints.

## Security Notes

- Do not commit API credentials.
- `get_config()` exposes only masked API key metadata.
- CLI config file uses restrictive permissions.

## Known Limits

- Only Porkbun is implemented as a concrete registrar client.
- No automatic DNS record provisioning is implemented in this repository yet.
- Rotation still performs real purchases through registrar APIs when configured;
  test against non-production credentials first.
