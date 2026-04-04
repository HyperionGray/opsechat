# Domain Rotation Guide

## Overview

OpSecChat supports domain rotation for burner email workflows. The current implementation focuses on:

- Porkbun API integration
- Budget-aware purchasing
- CLI-driven operations
- In-memory runtime manager with JSON-safe CLI state persistence

## What Was Implemented

`domain_manager.py` now exposes a complete manager interface used by the web/API layer and docs:

- `configure(api_key, secret_key, monthly_budget)`
- `get_config()`
- `search_cheap_domains(...)`
- `rotate_to_new_domain(...)` (structured result dict)
- `set_test_mode(...)`
- Compatibility helpers:
  - `budget_manager.*`
  - `generate_random_domain_name(...)`
  - `generate_domain_from_pattern(...)`

`domain_rotation_cli.py` now safely serializes/deserializes datetime values for persisted domain history.

## Prerequisites

1. Porkbun account and API credentials
2. Funds available in registrar account
3. A monthly budget set for rotation

## CLI Usage

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Notes

- `rotate` prompts for confirmation before purchase.
- Domain records are saved to `~/.opsechat/domain_config.json`.
- Timestamps in saved state are ISO-8601 strings and are restored to datetime objects on load.

## Python API Usage

```python
from domain_manager import domain_rotation_manager

# Configure Porkbun and budget
domain_rotation_manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_yyy",
    monthly_budget=25.0,
)

# Search candidate domains
options = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club"],
    max_price=3.00,
    limit=5,
)
print(options)

# Rotate with detailed result
result = domain_rotation_manager.rotate_to_new_domain(max_price=3.00)
print(result)
```

## Test Mode (No Real Purchases)

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.set_test_mode(True)
result = domain_rotation_manager.rotate_to_new_domain(max_price=2.50)
print(result)
```

In test mode, purchase calls are simulated and no registrar purchase request is made.

## Budget Compatibility Layer

Older examples referencing `budget_manager` remain supported:

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.budget_manager.set_monthly_budget(20.0)
print(domain_rotation_manager.budget_manager.get_month_spending())
print(domain_rotation_manager.budget_manager.get_remaining_budget())
```

## DNS Configuration Status

`configure_domain_dns(...)` exists as a compatibility placeholder and currently returns a "not implemented" response for the active registrar client. DNS operations should be performed in the registrar console until a registrar-specific DNS client is added.
