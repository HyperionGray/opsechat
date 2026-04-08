# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation utility for burner email workflows.
The implementation currently provides:

- Registrar integration via `PorkbunAPIClient`
- Budget-aware purchasing via `DomainRotationManager`
- A command-line wrapper: `domain_rotation_cli.py`
- Persisted state import/export for reliable CLI reloads

## Supported Registrars

Currently supported:

- **Porkbun** (recommended for low-cost TLDs)

Additional registrars can be added by implementing the `DomainAPIClient` interface.

## Setup

### 1) Get Porkbun API credentials

1. Sign in at [porkbun.com](https://porkbun.com)
2. Go to **Account -> API Access**
3. Enable API access and copy:
   - API Key
   - Secret API Key

### 2) Configure the CLI

```bash
python domain_rotation_cli.py config
```

This writes configuration to:

```text
~/.opsechat/domain_config.json
```

## CLI Usage

### Show status

```bash
python domain_rotation_cli.py status
```

### Search candidate domains

```bash
# Default search: max $5.00, 5 attempts
python domain_rotation_cli.py search

# Custom limits
python domain_rotation_cli.py search --max-price 3.00 --attempts 8
```

### Rotate to a new domain

```bash
# Interactive confirmation
python domain_rotation_cli.py rotate --max-price 2.50

# Non-interactive (automation-friendly)
python domain_rotation_cli.py rotate --max-price 2.50 --yes
```

### List owned domains

```bash
python domain_rotation_cli.py list
```

## Python API Usage

### Basic manager flow

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient("YOUR_API_KEY", "YOUR_SECRET")
manager = DomainRotationManager(client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=3.0, max_attempts=5)
if candidate:
    ok = manager.purchase_domain_if_budget_allows(candidate["domain"], candidate["price"])
    print("Purchased:", ok)

print("Active:", manager.get_active_domain())
print("Budget:", manager.get_budget_status())
```

### Rotate in one call

```python
new_domain = manager.rotate_domain()
if new_domain:
    print("Rotated to:", new_domain)
else:
    print("No purchase completed")
```

## Persisted State

`DomainRotationManager` provides:

- `export_state()` - returns a JSON-serializable dict
- `import_state(state)` - restores typed state (including datetimes)

State includes:

- `current_spending`
- `active_domain`
- `owned_domains` (ISO timestamps)

This supports robust behavior across CLI runs and automation jobs.

## Budget Safety Behavior

- Purchases are denied when they exceed `monthly_budget`
- Spend is tracked in `current_spending`
- Remaining budget is reported by `get_budget_status()`
- Rotation fails safely if no affordable domain is found

## Automation Example

Weekly non-interactive rotation:

```bash
0 2 * * 0 cd /path/to/opsechat && python domain_rotation_cli.py rotate --max-price 2.50 --yes
```

## Notes

- Domain purchases are real transactions; start with a small budget.
- Keep API credentials out of source control.
