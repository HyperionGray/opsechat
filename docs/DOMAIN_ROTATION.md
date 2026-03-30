# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. The domain manager now supports multiple registrars with provider-aware budget control and selection strategies.

## Supported Registrars

Currently implemented:
- Porkbun (`PorkbunAPIClient`)
- Namecheap (`NamecheapAPIClient`)

You can add more registrars by implementing `DomainAPIClient`.

## Core Concepts

### Provider Selection Strategies

`DomainRotationManager` supports:
- `round-robin`: rotate provider choice across registered providers and fail over if one cannot provide a suitable domain.
- `cheapest`: query all providers for a candidate and choose the lowest valid price.

### Budget Controls

Budget is enforced at two levels:
- Global monthly budget (`monthly_budget`)
- Optional per-provider budget (`provider_budgets`)

A domain purchase is denied unless both budgets allow it.

## Python Usage

### Single Provider (Backward-Compatible)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="pk1_xxx", api_secret="sk1_xxx")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

result = manager.rotate_to_new_domain(max_price=5.0, max_attempts=10)
print(result)
```

### Multi-Provider Setup

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient, NamecheapAPIClient

manager = DomainRotationManager(monthly_budget=50.0, selection_strategy="cheapest")

manager.add_provider(
    "porkbun",
    PorkbunAPIClient(api_key="pk1_xxx", api_secret="sk1_xxx"),
    monthly_budget=30.0,
)

manager.add_provider(
    "namecheap",
    NamecheapAPIClient(
        api_user="your-namecheap-api-user",
        api_key="your-namecheap-api-key",
        username="your-namecheap-username",
        client_ip="127.0.0.1",
    ),
    monthly_budget=20.0,
)

domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
print(domain_info)

rotate_result = manager.rotate_to_new_domain(max_price=5.0, max_attempts=10)
print(rotate_result)
```

### Inspect Current State

```python
config = manager.get_config()
budget = manager.get_budget_status()

print(config["providers"])
print(budget["provider_spending"])
```

## CLI Usage

Current CLI tool: `domain_rotation_cli.py`

```bash
# Configure Porkbun credentials
python domain_rotation_cli.py config

# Show budget/domain status
python domain_rotation_cli.py status

# Search cheap available domains
python domain_rotation_cli.py search

# Rotate to new domain
python domain_rotation_cli.py rotate

# List owned domains
python domain_rotation_cli.py list
```

Note: the CLI currently configures Porkbun directly. Multi-provider orchestration is available through the Python API and can be exposed in CLI commands later.

## Rotation Workflow

1. Register one or more providers.
2. Choose strategy (`round-robin` or `cheapest`).
3. Call `find_cheap_available_domain(...)`.
4. If candidate found, call `purchase_domain_if_budget_allows(...)` or `rotate_to_new_domain(...)`.
5. Inspect `get_budget_status()` for updated global and provider spending.

## Troubleshooting

### "No domain providers configured"

You created a manager with no providers. Register one using:
- `set_api_client(...)` for a single provider, or
- `add_provider(...)` for multi-provider.

### "Budget exceeded"

Check both:
- `monthly_budget` and `current_spending`
- per-provider values in `provider_budgets` and `provider_spending`

### Provider returns unavailable/empty price

The manager ignores candidates that are unavailable or do not provide a parseable price under `max_price`.

## Security Notes

- Keep registrar credentials out of source control.
- Use environment variables or secure secret injection for production.
- Use registrar-side account controls (IP restrictions, scoped keys) where available.
