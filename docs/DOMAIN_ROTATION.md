# Domain Rotation Guide

## Overview

`domain_manager.py` provides domain rotation support for burner email domains with:

- Porkbun API integration
- Budget-aware purchase controls
- Test mode (no real purchase)
- Serializable state export/load for CLI persistence

## Core Components

### `PorkbunAPIClient`

Registrar API client with:

- `search_domain(domain)`
- `purchase_domain(domain, years=1)`
- `get_pricing(tld)`
- `list_domains()`

### `DomainRotationManager`

Rotation and budget orchestration:

- `configure(api_key, secret_key, monthly_budget=50.0, provider="porkbun")`
- `get_config()`
- `set_test_mode(enabled)`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10, tlds=None)`
- `search_cheap_domains(tlds=None, max_price=5.0, limit=5, max_attempts_per_result=3)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_to_new_domain(max_price=5.0)` (structured response)
- `rotate_domain()` (legacy compatibility: returns domain string or `None`)
- `export_state()` / `load_state()`

## Structured Rotation Result

Prefer `rotate_to_new_domain()` for application/API paths:

```python
from domain_manager import DomainRotationManager

result = manager.rotate_to_new_domain(max_price=3.0)
if result["success"]:
    print("New domain:", result["domain"])
    print("Cost:", result["cost"])
else:
    print("Rotation failed:", result["error"])
```

Return shape:

- Success:
  - `{"success": True, "domain": "...", "cost": <float>, "test_mode": <bool>}`
- Failure:
  - `{"success": False, "domain": None, "error": "..."}`

## Budget Controls

Budget checks happen before purchase:

- Tracks `current_spending`
- Blocks purchases that exceed `monthly_budget`
- Exposes status via `get_budget_status()`

Example:

```python
status = manager.get_budget_status()
print(status["monthly_budget"], status["current_spending"], status["remaining"])
```

## Test Mode

Use test mode to validate flow without spending money:

```python
manager.set_test_mode(True)
result = manager.rotate_to_new_domain()
```

In test mode:

- Domain discovery still runs
- Registrar purchase is skipped
- Active domain is updated

## CLI Usage (`domain_rotation_cli.py`)

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

State persistence:

- Stored in `~/.opsechat/domain_config.json`
- Uses a serializable `domain_state` block
- Legacy keys are migrated on next successful save

## Security Notes

- API credentials are never persisted in this repository.
- Keep registrar keys in your local secure config only.
- Review spending limits regularly before enabling automatic rotation jobs.

