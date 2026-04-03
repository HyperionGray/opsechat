# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation workflow for burner email usage. It can:

- search for cheap available domains
- purchase within a monthly budget
- keep track of owned/active domains
- persist local state safely between CLI runs

Currently, Porkbun is the implemented registrar backend.

## CLI Commands

Use the CLI entrypoint:

```bash
python domain_rotation_cli.py <command>
```

Available commands:

- `config` - configure API key, API secret, and monthly budget
- `status` - show active domain and budget state
- `search` - try multiple cheap domain lookups
- `rotate` - find and purchase a new domain (interactive confirmation)
- `list` - list owned domains

## Persistence Model

The CLI stores its configuration and state in:

```text
~/.opsechat/domain_config.json
```

Stored fields include:

- `api_key`
- `api_secret`
- `monthly_budget`
- `current_spending`
- `owned_domains`
- `active_domain`

Timestamp fields (`purchased_at`, `expires_at`) are serialized in ISO-8601 format and normalized back to `datetime` objects when loaded.

On load/save, expired domains are pruned automatically and the active domain is reconciled so it always points to a currently owned domain (or `None`).

## Programmatic Usage

Use `DomainRotationManager` from `domain_manager.py`:

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("api_key", "api_secret")
manager = DomainRotationManager(api_client=client, monthly_budget=25.0)

candidate = manager.find_cheap_available_domain(max_price=5.0)
if candidate:
    ok = manager.purchase_domain_if_budget_allows(candidate["domain"], candidate["price"])
    if ok:
        print("Active domain:", manager.get_active_domain())
        print("Budget:", manager.get_budget_status())
```

Useful manager methods:

- `generate_random_domain(tld="xyz", length=8)`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_domain()`
- `get_budget_status()`
- `get_owned_domains()`
- `serialize_state()`
- `load_state(state)`
- `prune_expired_domains()`

## Budget and Safety Notes

- Purchases are blocked if `current_spending + price > monthly_budget`.
- The default budget is `$50.0` unless configured.
- Domain search prioritizes inexpensive TLDs (`xyz`, `club`, `online`, `site`, `website`).

## Troubleshooting

### "API credentials not configured"

Run:

```bash
python domain_rotation_cli.py config
```

### Budget exceeded

Increase the monthly budget in `config`, or wait for your normal budget-reset process.

### No cheap domain found

Retry `search`/`rotate`, increase max acceptable price, or try again later as availability varies.
