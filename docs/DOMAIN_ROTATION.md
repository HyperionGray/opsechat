# Domain Rotation Guide

## Overview

`domain_manager.py` and `domain_rotation_cli.py` provide automated burner-domain rotation with:

- registrar API abstraction (`DomainAPIClient`)
- concrete clients for **Porkbun** and **Namecheap**
- monthly budget enforcement
- in-memory tracking of owned and active domains
- CLI state persistence under `~/.opsechat/domain_config.json`

This document reflects the current implementation in the repository.

## Supported Registrars

- Porkbun (JSON API)
- Namecheap (XML API)

Additional registrars can be added by implementing `DomainAPIClient` and registering via:

```python
manager.add_api_client("provider-name", client, set_active=True)
```

## CLI Quick Start

```bash
# Interactive setup (provider, credentials, budget)
python domain_rotation_cli.py config

# Inspect current budget/domain status
python domain_rotation_cli.py status

# Search for low-cost available domains
python domain_rotation_cli.py search

# Rotate to a newly purchased domain
python domain_rotation_cli.py rotate

# List owned domains
python domain_rotation_cli.py list
```

## Configuration Notes

### Porkbun

Required:
- `api_key`
- `api_secret`

### Namecheap

Required:
- `api_key`
- `api_user`

Optional:
- `username` (defaults to `api_user`)
- `client_ip` (defaults to `127.0.0.1`, must be API-whitelisted in Namecheap)

## Programmatic Usage

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="...", api_secret="...")
manager = DomainRotationManager(monthly_budget=20.0)
manager.add_api_client("porkbun", client, set_active=True)

candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
if candidate:
    manager.purchase_domain_if_budget_allows(candidate["domain"], candidate["price"])
    print("Active:", manager.get_active_domain())
```

Provider switching:

```python
from domain_manager import NamecheapAPIClient

manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(api_key="...", api_user="...", client_ip="x.x.x.x"),
)
manager.set_active_provider("namecheap")
```

## Budget Controls

Budget checks happen before purchase:

- if `current_spending + price > monthly_budget`, purchase is blocked
- successful purchase increments `current_spending`
- budget summary available via `get_budget_status()`

## State Serialization

`DomainRotationManager` supports safe persistence helpers:

- `get_owned_domains_serializable()` converts datetimes to ISO-8601 strings
- `load_owned_domains()` restores datetime objects from serialized entries

The CLI uses these helpers to avoid JSON serialization errors and to preserve timestamps.

## Security Guidance

- Never commit API keys.
- Prefer environment-local configuration and restricted file permissions.
- Validate Namecheap client IP allowlisting before production use.
- Start with conservative budgets while testing automation behavior.
