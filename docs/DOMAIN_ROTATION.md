# Domain Rotation Guide

## Overview

OpSecChat includes domain rotation utilities for burner-email workflows. The feature centers on:

- `domain_manager.py` for API client and rotation logic
- `python -m domain_manager` for scriptable CLI usage
- `domain_rotation_cli.py` for interactive credential setup and operator workflows

Current registrar implementation:

- Porkbun API (`PorkbunAPIClient`)

## Setup

### 1) Create Porkbun API credentials

1. Sign in at https://porkbun.com
2. Open Account -> API Access
3. Enable API and collect:
   - API key
   - Secret API key

### 2) Configure environment variables

```bash
export PORKBUN_API_KEY="pk1_xxx"
export PORKBUN_SECRET_KEY="sk1_xxx"
export DOMAIN_BUDGET="20"
```

Optional:

```bash
export DOMAIN_MANAGER_STATE_FILE="$HOME/.opsechat/domain-state.json"
```

## Python API Usage

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("pk1_xxx", "sk1_xxx")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=3.0, max_attempts=10)
print(candidate)

new_domain = manager.rotate_domain(max_price=3.0, max_attempts=10)
print(new_domain)

print(manager.get_budget_status())
```

Backward-compatible aliases are available for legacy scripts:

- `rotate_to_new_domain()` -> `rotate_domain()`
- `generate_random_domain_name()` -> `generate_random_domain()`

## Module CLI (`python -m domain_manager`)

The module CLI is stateful through a JSON file (default: `.domain-manager-state.json`).

### Search for an available cheap domain

```bash
python -m domain_manager \
  --api-key "$PORKBUN_API_KEY" \
  --api-secret "$PORKBUN_SECRET_KEY" \
  search --max-price 3.0 --max-attempts 10 --tld xyz --tld club
```

### Rotate to a newly purchased domain

```bash
python -m domain_manager \
  --api-key "$PORKBUN_API_KEY" \
  --api-secret "$PORKBUN_SECRET_KEY" \
  rotate --max-price 3.0 --max-attempts 10
```

### Purchase a specific domain

```bash
python -m domain_manager \
  --api-key "$PORKBUN_API_KEY" \
  --api-secret "$PORKBUN_SECRET_KEY" \
  purchase --domain example.xyz --price 2.50
```

If `--price` is omitted, the CLI queries availability and pricing from the API first.

### Budget management

```bash
python -m domain_manager budget status
python -m domain_manager budget set --amount 25
```

### List locally recorded domains

```bash
python -m domain_manager list
```

## Interactive Operator CLI (`domain_rotation_cli.py`)

Use this tool for guided credential setup and day-to-day operations:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

`domain_rotation_cli.py` now uses datetime-safe state serialization through `DomainRotationManager.export_state()` and `load_state()`.

## Persisted State Format

State files store:

- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains[]` with ISO-8601 timestamps

Example:

```json
{
  "monthly_budget": 25.0,
  "current_spending": 3.5,
  "active_domain": "abc123.xyz",
  "owned_domains": [
    {
      "domain": "abc123.xyz",
      "price": 3.5,
      "purchased_at": "2026-03-18T10:15:00",
      "expires_at": "2027-03-18T10:15:00"
    }
  ]
}
```

## Notes

- Domain purchases are real purchases when valid API keys are used.
- Budget checks are enforced before purchasing.
- Keep API credentials out of source control.
