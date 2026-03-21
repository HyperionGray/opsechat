# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation module for burner email workflows:

- `domain_manager.py` contains:
  - `DomainAPIClient` (base registrar API interface)
  - `PorkbunAPIClient` (Porkbun implementation)
  - `DomainRotationManager` (budget-aware search/purchase/rotation logic)
- `domain_rotation_cli.py` provides the user-facing CLI.

## CLI Quick Start

Configure credentials:

```bash
python domain_rotation_cli.py config
```

Check status:

```bash
python domain_rotation_cli.py status
```

Search for cheap available domains:

```bash
python domain_rotation_cli.py search
```

Rotate to a new domain (interactive confirmation):

```bash
python domain_rotation_cli.py rotate
```

List owned domains:

```bash
python domain_rotation_cli.py list
```

## State Persistence

CLI state is stored in:

```text
~/.opsechat/domain_config.json
```

The manager persists:

- `current_spending`
- `owned_domains`
- `active_domain`
- `budget_period_start`

Timestamps are serialized as ISO-8601 strings and parsed back on load.

### Monthly Budget Window

`monthly_budget` is calendar-month aware:

- Spending is tracked within a month window.
- When the month changes, spend automatically resets to `0.0`.
- `status` output includes the current budget window start date.

This prevents stale spending values from previous months from blocking new purchases.

## Python API Usage

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="pk1_...", api_secret="sk1_...")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

domain = manager.rotate_domain()
print("Active domain:", domain)
print(manager.get_budget_status())
```

## Extending to Another Registrar

Implement a subclass of `DomainAPIClient`:

- `search_domain(domain: str) -> dict`
- `purchase_domain(domain: str, years: int = 1) -> dict`
- `get_pricing(tld: str) -> dict`

Then inject it into `DomainRotationManager`.

## Troubleshooting

### `list` shows unknown/invalid dates

Old config files may contain non-ISO date values. Re-run `rotate` once to persist normalized state.

### Budget seems stuck

Run `status` and verify `Window Start`. If your config file has an invalid `budget_period_start`, the manager will normalize it automatically.

### Purchase fails

Check:

- API credentials (`config` command)
- Remaining budget (`status` command)
- Registrar API reachability (network/firewall)
