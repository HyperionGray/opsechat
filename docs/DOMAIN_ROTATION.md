# Domain Rotation Guide

## Overview

OpSecChat includes domain rotation support for burner email workflows.
The current implementation focuses on:

- Porkbun API integration (`PorkbunAPIClient`)
- Budget-aware domain purchase flow
- Persistent local CLI state
- Automatic monthly budget-cycle reset

## What Exists Today

The active domain rotation components are:

- `domain_manager.py`
  - `DomainAPIClient` (abstract base for registrars)
  - `PorkbunAPIClient`
  - `DomainRotationManager`
- `domain_rotation_cli.py`
  - `config`
  - `status`
  - `search`
  - `rotate`
  - `list`

## Setup

### 1) Create Porkbun API Credentials

1. Sign in at [porkbun.com](https://porkbun.com)
2. Open **Account -> API Access**
3. Create API key pair
4. Keep both values:
   - API Key
   - Secret API Key

### 2) Configure the CLI

```bash
python domain_rotation_cli.py config
```

The CLI stores configuration in:

```text
~/.opsechat/domain_config.json
```

Permissions are set to `0600`.

## CLI Usage

```bash
# Show status and budget
python domain_rotation_cli.py status

# Search for cheap domains
python domain_rotation_cli.py search

# Purchase and rotate to a new domain
python domain_rotation_cli.py rotate

# List owned domains
python domain_rotation_cli.py list
```

## Runtime Behavior

### Cheap Domain Search

`DomainRotationManager.find_cheap_available_domain()`:

- tries random domain names
- uses low-cost TLD pool (`xyz`, `club`, `online`, `site`, `website`)
- parses registrar prices robustly (numeric or currency-formatted strings)
- returns the first available candidate within the configured max price

### Budget Enforcement

`purchase_domain_if_budget_allows()`:

- normalizes the input price
- checks budget before purchase
- records successful purchase metadata:
  - domain
  - price
  - purchased timestamp
  - expiration timestamp
  - optional registrar order id

### Monthly Budget Cycle Reset

Budget spending is tracked by cycle key (`YYYY-MM`, UTC).
When the cycle changes, spend is reset automatically.

This happens during:

- `get_budget_status()`
- `purchase_domain_if_budget_allows()`
- `export_state()`

## State Persistence Model

The manager now supports explicit state lifecycle methods:

- `restore_state(state_dict)`
- `export_state()`

This supports safe persistence for CLI config and backward compatibility with older mixed-format records.

### Normalization on Restore

- `current_spending` is normalized to float
- `owned_domains` records are validated and normalized
- datetime strings are parsed into runtime `datetime` objects
- invalid or partial records are skipped safely

### Serialization on Export

- records are emitted as JSON-safe structures
- datetime values are serialized as strings
- `last_budget_reset` is persisted

## Python API Example

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient(api_key="YOUR_KEY", api_secret="YOUR_SECRET")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
if candidate:
    purchased = manager.purchase_domain_if_budget_allows(
        candidate["domain"],
        candidate["price"]
    )
    print("Purchased:", purchased)

print(manager.get_budget_status())
print(manager.export_state())
```

## Extending to Other Registrars

Create a subclass of `DomainAPIClient` and implement:

- `search_domain(domain: str) -> Dict`
- `purchase_domain(domain: str, years: int = 1) -> Dict`
- `get_pricing(tld: str) -> Dict`

Then pass your client into `DomainRotationManager(api_client=...)`.

## Troubleshooting

### "No API client configured"

Cause:
- manager was created without an API client

Fix:
- configure CLI credentials (`python domain_rotation_cli.py config`)
- or construct `DomainRotationManager` with a registrar client

### "Invalid domain price"

Cause:
- registrar returned an unexpected price format

Fix:
- inspect registrar response payload
- ensure `price` is parseable as numeric/currency string

### Budget appears exhausted at month rollover

Cause:
- stale state not refreshed yet

Fix:
- run `status` or any purchase operation (cycle check runs automatically)
- confirm `last_budget_reset` in persisted state
