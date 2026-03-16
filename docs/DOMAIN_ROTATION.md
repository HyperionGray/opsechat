# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation subsystem for burner email domains with:

- budget-aware purchasing
- random low-cost domain generation
- persisted local state via CLI config
- pluggable registrar clients

## Supported registrars

- `porkbun` (recommended default)
- `namecheap` (newly supported)

Both are exposed through `DomainAPIClient` implementations in `domain_manager.py`.

## CLI quickstart

Use the CLI wrapper:

```bash
python domain_rotation_cli.py providers
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

Optional provider override per command:

```bash
python domain_rotation_cli.py status --provider namecheap
python domain_rotation_cli.py search --provider porkbun
```

## Provider setup

### Porkbun

Required:
- API key
- API secret

CLI command:

```bash
python domain_rotation_cli.py config --provider porkbun
```

### Namecheap

Required:
- username
- API key
- client IP (allowed in Namecheap API access settings)

Optional but needed for purchases:
- default contact profile (`first_name`, `last_name`, `address1`, `city`, `state`, `postal_code`, `country`, `phone`, `email`)

CLI command:

```bash
python domain_rotation_cli.py config --provider namecheap
```

## Python API usage

### Create provider clients

```python
from domain_manager import create_domain_api_client

porkbun = create_domain_api_client(
    "porkbun",
    api_key="YOUR_PORKBUN_KEY",
    api_secret="YOUR_PORKBUN_SECRET",
)

namecheap = create_domain_api_client(
    "namecheap",
    api_key="YOUR_NAMECHEAP_KEY",
    username="YOUR_NAMECHEAP_USERNAME",
    client_ip="203.0.113.10",
)
```

### Run rotation with budget controls

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(api_client=porkbun, monthly_budget=20.0)
new_domain = manager.rotate_domain()
print(new_domain)
```

## State persistence behavior

`domain_rotation_cli.py` persists:

- `current_spending`
- `owned_domains`
- `active_domain`
- selected provider and credentials

Datetime fields are serialized to ISO strings when saving and parsed when loading.

## Notes

- Namecheap search and pricing work out of the box.
- Namecheap purchases require contact profile fields because the upstream API requires contact data.
- If a provider search response does not include price, OpSecChat attempts provider pricing lookup before making budget decisions.
