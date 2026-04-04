# Domain Rotation Guide

## Overview

OpSecChat includes domain rotation support for burner email workflows using registrar APIs.
The current implementation supports Porkbun and focuses on:

- finding cheap available domains
- purchasing within a monthly budget
- tracking owned domains and active domain
- persisting rotation state safely through JSON serialization

## Current API Surface

The `DomainRotationManager` supports the following production methods:

- `configure(api_key, secret_key|api_secret, monthly_budget)`
- `get_config()`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_domain()`
- `get_budget_status()`
- `get_owned_domains()`
- `export_state()`
- `import_state(state)`

## CLI Usage

Use `domain_rotation_cli.py` for operator workflows:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### What changed recently

State persistence now uses manager-native helpers:

- save path: `manager.export_state()` -> JSON config file
- load path: JSON config file -> `manager.import_state(...)`

This avoids datetime serialization failures when saving or loading owned domain history.

## Web App Integration

`email_security_routes.py` calls:

- `domain_rotation_manager.get_config()`
- `domain_rotation_manager.configure(...)`
- `domain_rotation_manager.rotate_domain()`

The manager now provides these methods for compatibility with that route layer.

## Budget and Safety Behavior

- Purchases are blocked if `current_spending + price > monthly_budget`
- Price parsing handles numeric values and common currency strings (`$`, `€`, commas)
- Invalid price inputs are rejected before purchase attempts

## Quick Example

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=20.0)
manager.configure(
    api_key="pk1_example",
    secret_key="sk1_example",
    monthly_budget=25.0
)

new_domain = manager.rotate_domain()
print("New active domain:", new_domain)
print("Budget:", manager.get_budget_status())
```

## Notes

- API secrets should be treated as sensitive credentials and never committed.
- CLI configuration file permissions are set to `0600`.
- This feature performs real registrar purchases when valid credentials are configured.
