# Domain Rotation Guide

## Overview

OpSecChat includes a domain-rotation module for purchasing low-cost domains (via Porkbun) and tracking spending against a monthly budget.

Implemented components:

- `domain_manager.py`
  - `PorkbunAPIClient` (registrar API client)
  - `DomainRotationManager` (budget, purchase, active domain, persisted state helpers)
- `domain_rotation_cli.py`
  - Interactive CLI for configuring API credentials and rotating domains

## Supported registrar

- Porkbun (`https://porkbun.com/api/json/v3`)

The manager is extensible through the `DomainAPIClient` abstract base class.

## Configure credentials and budget (CLI)

```bash
python domain_rotation_cli.py config
```

The CLI stores config at:

```text
~/.opsechat/domain_config.json
```

Stored fields:

- `api_key`
- `api_secret`
- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains` (with ISO timestamps)

The config file is written with `0600` permissions.

## CLI commands

### Show current status

```bash
python domain_rotation_cli.py status
```

### Search for low-cost available domains (no purchase)

```bash
python domain_rotation_cli.py search
```

### Rotate (find + purchase + activate)

```bash
python domain_rotation_cli.py rotate
```

### List purchased domains

```bash
python domain_rotation_cli.py list
```

## Programmatic usage

### Configure the global manager

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_yyy",
    monthly_budget=20.0,
)

print(domain_rotation_manager.get_config())
```

`configure(...)` accepts either `api_secret=` or `secret_key=`.

### Rotate domain

```python
new_domain = domain_rotation_manager.rotate_domain()
if new_domain:
    print(f"Active domain: {new_domain}")
else:
    print("Rotation failed")
```

### Budget and state info

```python
budget = domain_rotation_manager.get_budget_status()
print(budget["remaining"])

print(domain_rotation_manager.get_active_domain())
print(domain_rotation_manager.get_owned_domains())
```

### Persist state safely

Use `export_state()` / `load_state()` when writing manager state to JSON:

```python
state = domain_rotation_manager.export_state()  # JSON-safe (ISO datetime strings)
# ... save JSON ...

domain_rotation_manager.load_state(state)       # restores datetime fields
```

## Budget behavior

- Purchases are rejected when `current_spending + price > monthly_budget`.
- Invalid/unparseable prices are rejected.
- `find_cheap_available_domain(...)` skips registrar responses with invalid prices.

## Price parsing behavior

The manager normalizes common registrar formats:

- `2.99`
- `"$2.99 USD"`
- `"1,234.56"`

If parsing fails, price is treated as invalid and the domain is skipped or purchase is denied.

## Web integration notes

The email security routes (`email_security_routes.py`) call:

- `domain_rotation_manager.configure(...)`
- `domain_rotation_manager.get_config()`
- `domain_rotation_manager.rotate_domain()`

These interfaces are implemented in `DomainRotationManager`.

## Security notes

- Do not commit real API credentials.
- Use low-privilege registrar credentials where possible.
- Domain purchases are real transactions.

