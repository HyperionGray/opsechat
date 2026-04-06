# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation subsystem for burner email workflows.
It can:

- Check domain availability via registrar APIs
- Find low-cost random domains on cheap TLDs
- Purchase a domain when it fits budget constraints
- Persist local rotation state for the CLI (`active_domain`, spending, owned domains)

Currently implemented registrar client:

- `PorkbunAPIClient` (`domain_manager.py`)

## Quick Start (CLI)

### 1. Configure credentials and budget

```bash
python domain_rotation_cli.py config
```

This stores config at:

```text
~/.opsechat/domain_config.json
```

with secure file permissions (`0600`).

### 2. Check current status

```bash
python domain_rotation_cli.py status
```

### 3. Search for cheap available domains

```bash
python domain_rotation_cli.py search
```

### 4. Rotate (find + purchase + activate)

```bash
python domain_rotation_cli.py rotate
```

### 5. List owned domains

```bash
python domain_rotation_cli.py list
```

## State Persistence

The CLI persists runtime manager state in the same config file:

- `current_spending`
- `owned_domains`
- `active_domain`

`DomainRotationManager.export_state()` serializes datetimes to ISO8601 strings.
`DomainRotationManager.import_state()` restores datetime objects and safely skips
invalid entries instead of crashing.

This keeps `list` and `status` working across CLI runs.

## Programmatic Usage

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient(api_key="pk1_...", api_secret="sk1_...")
manager = DomainRotationManager(api_client=client, monthly_budget=10.0)

domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
if domain_info:
    print("Found:", domain_info["domain"], "price:", domain_info["price"])

    if manager.purchase_domain_if_budget_allows(
        domain_info["domain"], domain_info["price"]
    ):
        print("Active domain:", manager.get_active_domain())
        print("Budget status:", manager.get_budget_status())
```

## Extending to Other Registrars

Implement a new client by subclassing `DomainAPIClient` and implementing:

- `search_domain(domain)`
- `purchase_domain(domain, years=1)`
- `get_pricing(tld)`

Example skeleton:

```python
from domain_manager import DomainAPIClient


class NamecheapAPIClient(DomainAPIClient):
    def search_domain(self, domain: str):
        # Implement registrar-specific availability lookup
        return {}

    def purchase_domain(self, domain: str, years: int = 1):
        # Implement registrar-specific purchase endpoint
        return {"success": False}

    def get_pricing(self, tld: str):
        # Implement registrar-specific pricing lookup
        return {}
```

## Budget Behavior

- Purchases that exceed `monthly_budget` are denied
- Spending is tracked via `current_spending`
- Budget status reports: `monthly_budget`, `current_spending`, `remaining`, `domains_owned`

## Safety Notes

- Do not commit API credentials to git
- Use dedicated API keys with least privilege if supported
- Domain purchases are real operations and can incur charges
- Prefer test credentials or a low budget while validating setup
