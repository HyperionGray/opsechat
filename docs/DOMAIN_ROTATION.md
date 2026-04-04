# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. Domain rotation helps avoid domain blocklists and reduces long-term exposure of any single burner domain.

Current implementation focuses on:
- Domain availability search
- Budget-aware purchase
- Provider-aware selection strategies
- CLI-driven workflow

## Supported Providers

Implemented provider:
- **Porkbun** via `PorkbunAPIClient`

Architecture:
- The `DomainAPIClient` base class is now a formal abstract interface.
- Additional providers can be added by implementing the interface and registering them with `DomainRotationManager.add_api_client(...)`.

## Provider Selection Strategies

`DomainRotationManager` supports two built-in provider strategies:

1. `priority` (default)
   - Checks providers in configured order.
   - Uses the first provider that has an available domain at/under your max price.
   - Good when you trust a preferred provider and want simple failover.

2. `cheapest`
   - Checks all configured providers for the generated candidate.
   - Selects the lowest valid price.
   - Good when minimizing cost is the primary goal.

Each purchase record tracks which provider was used.

## Core Python API

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

primary = PorkbunAPIClient("pk_live_1", "sk_live_1")
backup = PorkbunAPIClient("pk_live_2", "sk_live_2")

manager = DomainRotationManager(monthly_budget=20.0, provider_strategy="priority")
manager.add_api_client("primary", primary, make_primary=True)
manager.add_api_client("backup", backup)

# Search for a candidate
candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=5)
print(candidate)

# Rotate (search + purchase + activate)
new_domain = manager.rotate_domain()
print(new_domain)
```

You can override strategy per call:

```python
candidate = manager.find_cheap_available_domain(
    max_price=5.0,
    max_attempts=5,
    provider_strategy="cheapest",
)
```

## CLI Workflow

Use `domain_rotation_cli.py` for day-to-day operations:

```bash
# Configure API key, secret, budget, and provider strategy
python domain_rotation_cli.py config

# Show budget + active domain
python domain_rotation_cli.py status

# Search for cheap domains
python domain_rotation_cli.py search

# Purchase and rotate to a new domain
python domain_rotation_cli.py rotate

# List owned domains and timestamps
python domain_rotation_cli.py list
```

Configuration is stored at:
- `~/.opsechat/domain_config.json`

Important implementation details:
- `provider_strategy` is persisted and validated (`priority` or `cheapest`).
- Owned domain timestamps are serialized/deserialized as ISO datetimes, so `list` remains stable after reload.

## Budget Behavior

Budget checks happen before purchase:
- Purchase is denied if `current_spending + price > monthly_budget`.
- Spending and owned domains are updated only after successful purchase.

Quick status fields:
- `monthly_budget`
- `current_spending`
- `remaining`
- `domains_owned`

## Recommended Operational Pattern

1. Start with `priority` strategy and one provider.
2. Add a second provider for resilience.
3. Switch to `cheapest` strategy if cost optimization is needed.
4. Keep monthly budget conservative until live behavior is validated.

## Extending With a New Provider

Create a class implementing `DomainAPIClient`:

```python
from domain_manager import DomainAPIClient

class ExampleRegistrarClient(DomainAPIClient):
    def search_domain(self, domain: str):
        ...

    def purchase_domain(self, domain: str, years: int = 1):
        ...

    def get_pricing(self, tld: str):
        ...
```

Then register it:

```python
manager.add_api_client("example", ExampleRegistrarClient("api-key"), make_primary=False)
```

## Troubleshooting

### "No API client configured"
- Ensure at least one provider is registered (or configured through CLI).

### "Invalid provider strategy"
- Valid values are only `priority` and `cheapest`.
- Re-run `python domain_rotation_cli.py config` to correct persisted config.

### "Could not find available cheap domain"
- Increase `max_attempts`.
- Increase `max_price`.
- Retry later if provider API is rate-limited or degraded.
