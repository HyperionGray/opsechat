# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows using the
`domain_manager.py` module and `domain_rotation_cli.py`.

The current implementation focuses on:
- Porkbun API integration
- Budget-aware purchases
- State persistence in CLI config
- Safe serialization of owned domain metadata

## Supported Registrar

- Porkbun (implemented)

The API layer is extensible via `DomainAPIClient`.

## CLI Setup

### 1. Configure API credentials

```bash
python domain_rotation_cli.py config
```

This stores credentials and local state at:

`~/.opsechat/domain_config.json`

File permissions are restricted to `0600`.

### 2. Check current status

```bash
python domain_rotation_cli.py status
```

### 3. Search for cheap available domains

```bash
python domain_rotation_cli.py search
```

### 4. Purchase and rotate

```bash
python domain_rotation_cli.py rotate
```

### 5. List owned domains

```bash
python domain_rotation_cli.py list
```

## Python API Usage

### Configure at runtime

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_your_key",
    secret_key="sk1_your_secret",
    monthly_budget=20.0,
)
```

### Read non-sensitive config/status

```python
status = domain_rotation_manager.get_config()
print(status["configured"])
print(status["monthly_budget"])
print(status["api_key_last4"])  # only last 4 chars are exposed
```

### Rotate domain

```python
result = domain_rotation_manager.rotate_domain()
if result["success"]:
    print("New domain:", result["domain"])
    print("Price:", result.get("price"))
else:
    print("Rotation failed:", result["error"])
```

`rotate_domain()` returns:
- `{"success": True, "domain": "...", "price": <float>}` on success
- `{"success": False, "domain": None, "error": "..."}` on failure

## Budget Behavior

- Purchases are blocked when `current_spending + price > monthly_budget`
- Default monthly budget is `50.0`
- Budget status can be fetched via `get_budget_status()`

## State Import/Export

`DomainRotationManager` provides:
- `export_state()` -> JSON-serializable state
- `import_state(state)` -> restores runtime state

This is used by the CLI so owned domain entries survive restarts.
Datetime fields are safely serialized to ISO-8601 and restored on import.

## Security Notes

- Do not commit API credentials to git.
- Prefer environment-specific credential handling for production deployments.
- Domain purchases are real billable actions with Porkbun.

