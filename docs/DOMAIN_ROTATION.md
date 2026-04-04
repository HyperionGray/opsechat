# Domain Rotation Guide

## Overview

OpSecChat supports automated burner-domain rotation through `domain_manager.py`
and the `domain_rotation_cli.py` helper.

Current provider support:
- Porkbun API (implemented)
- Additional providers can be added by subclassing `DomainAPIClient`

## Configure Domain Rotation

Use either the web config page or the CLI.

### Web Configuration

1. Open `/<secret-path>/email/config`
2. Enter:
   - Porkbun API key
   - Porkbun secret key
   - Monthly budget (USD)
3. Save

The backend calls:
- `domain_rotation_manager.configure(...)`
- `domain_rotation_manager.get_config()`

### CLI Configuration

```bash
python domain_rotation_cli.py config
```

Config is stored at:
- `~/.opsechat/domain_config.json` (permission mode `0600`)

## Runtime Features

The `DomainRotationManager` provides:

- Domain generation:
  - `generate_random_domain(tld="xyz", length=8)`
  - `generate_random_domain_name(...)` (compatibility alias)
- Cheap domain search:
  - `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
  - `search_cheap_domains(tlds=None, max_price=5.0, limit=10)`
- Purchase and rotation:
  - `purchase_domain_if_budget_allows(domain, price)`
  - `rotate_domain()` -> active domain string or `None`
  - `rotate_to_new_domain()` -> structured response dict
- Config and state:
  - `configure(...)`
  - `get_config()`
  - `export_state()` / `load_state(...)`

## Budget Management

Budget APIs:

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.budget_manager.set_monthly_budget(20.0)
spent = domain_rotation_manager.budget_manager.get_month_spending()
remaining = domain_rotation_manager.budget_manager.get_remaining_budget()
```

Budget enforcement happens in `purchase_domain_if_budget_allows`.

## CLI Commands

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Notes about persistence

The CLI persists owned-domain state across runs using manager helpers:
- Datetimes are serialized to ISO8601 strings (`export_state`)
- Datetimes are rehydrated on load (`load_state`)

This avoids JSON serialization failures when domains have `datetime` metadata.

## Programmatic Example

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_yyy",
    monthly_budget=15.0
)

candidates = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=3.0,
    limit=5
)
print(candidates)

result = domain_rotation_manager.rotate_to_new_domain()
print(result)
```

## Test Mode

To simulate purchases without hitting provider billing:

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.set_test_mode(True)
result = domain_rotation_manager.rotate_to_new_domain()
print(result)
```

## Security Notes

- Never commit API credentials.
- Store credentials only in local runtime config or secret management.
- Keep budgets low by default and review spending regularly.
