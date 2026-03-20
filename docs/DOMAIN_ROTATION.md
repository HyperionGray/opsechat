# Domain Rotation Guide

## Overview

OpSecChat supports automated burner-domain rotation with multiple registrar providers.
Current providers:

- Porkbun
- Namecheap

The domain manager can search across providers, pick an affordable available domain, and purchase within a configured monthly budget.

## Quick Start (CLI)

Configure at least one provider:

```bash
python domain_rotation_cli.py config
```

Check current status:

```bash
python domain_rotation_cli.py status
```

Search for available domains:

```bash
python domain_rotation_cli.py search
python domain_rotation_cli.py search --provider porkbun
python domain_rotation_cli.py search --provider namecheap
```

Rotate to a newly purchased domain:

```bash
python domain_rotation_cli.py rotate
python domain_rotation_cli.py rotate --provider porkbun
python domain_rotation_cli.py rotate --provider namecheap
```

List purchased domains:

```bash
python domain_rotation_cli.py list
```

## Provider Configuration Notes

### Porkbun

Required fields:

- `api_key`
- `api_secret`

Reference:

- https://porkbun.com/account/api

### Namecheap

Required fields:

- `api_key`
- `username`
- `client_ip` (must be allowlisted in Namecheap API settings)

Optional field:

- `api_user` (defaults to `username`)

Reference:

- https://www.namecheap.com/support/api/intro/

## Multi-Provider Behavior

The domain manager keeps an ordered provider list and tries each provider during search.
If a provider does not return availability or usable pricing, the manager falls back to the next provider.

Returned search metadata includes:

- selected `provider`
- computed `price`
- chosen `domain`
- `tld`

## Budget and State Persistence

The CLI stores:

- monthly budget
- configured providers
- active domain/provider
- purchase history

State is JSON-safe. Datetime fields (`purchased_at`, `expires_at`) are serialized to ISO-8601 when written and parsed back when read.

## Python API Example

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient, NamecheapAPIClient

manager = DomainRotationManager(monthly_budget=25.0)
manager.add_api_client("porkbun", PorkbunAPIClient("pk_key", "pk_secret"), set_primary=True)
manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(api_key="nc_key", username="nc_user", client_ip="203.0.113.10"),
)

domain = manager.rotate_domain()
print("Active domain:", domain)
print("Budget status:", manager.get_budget_status())
```

## Security Guidance

- Never commit registrar keys.
- Use separate registrar accounts or keys for testing and production.
- Set conservative monthly budget limits.
- Review purchased-domain history regularly.
