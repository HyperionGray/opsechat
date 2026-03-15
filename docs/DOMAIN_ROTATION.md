# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation module for burner email workflows.  
It can:

- Search for low-cost available domains
- Purchase domains through Porkbun
- Track monthly spend against a budget
- Rotate the active domain

Core module: `domain_manager.py`  
CLI tool: `domain_rotation_cli.py`

---

## Supported Registrar

- **Porkbun** (`PorkbunAPIClient`)

`DomainAPIClient` can be extended for other registrars later.

---

## Python API

### Basic setup

```python
from domain_manager import domain_rotation_manager

# Configure API credentials and budget
domain_rotation_manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_yyy",
    monthly_budget=10.0,
)
```

### Check configuration state

```python
config = domain_rotation_manager.get_config()
print(config["configured"], config["monthly_budget"])
```

### Search for cheap domains

```python
matches = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=3.00,
    limit=5,
    max_attempts=20,
)
for item in matches:
    print(item["domain"], item["price"])
```

### Rotate with structured result

```python
result = domain_rotation_manager.rotate_to_new_domain(max_price=5.0)
if result["success"]:
    print("Active domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

### Compatibility helpers

```python
# Legacy return type (str|None)
active_domain = domain_rotation_manager.rotate_domain()

# Toggle dry-run behavior (no purchase/spend)
domain_rotation_manager.set_test_mode(True)
```

---

## CLI Usage

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Notes

- `config` stores credentials in `~/.opsechat/domain_config.json` with mode `600`.
- CLI state now safely serializes domain timestamps to ISO-8601.
- `rotate` prompts before purchase.

---

## Budget Behavior

- Purchases are blocked when `current_spending + price > monthly_budget`
- `get_budget_status()` returns:
  - `monthly_budget`
  - `current_spending`
  - `remaining`
  - `domains_owned`

---

## Security Notes

- Never commit registrar credentials.
- Prefer environment-injected secrets for automation.
- Use `set_test_mode(True)` when validating workflows to avoid unintended purchases.
