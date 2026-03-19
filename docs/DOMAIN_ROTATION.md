# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows.
The implementation currently supports two registrars:

- Porkbun
- Namecheap

Domain rotation includes:

- random candidate generation
- availability checks
- budget-aware purchasing
- active-domain tracking

## Quick Start

### CLI workflow

```bash
# Configure credentials (interactive)
python domain_rotation_cli.py config

# Configure Namecheap explicitly (optional)
python domain_rotation_cli.py config --registrar namecheap --sandbox

# Check status and budget
python domain_rotation_cli.py status

# Search for cheap domains
python domain_rotation_cli.py search

# Purchase and rotate to a new active domain
python domain_rotation_cli.py rotate

# List purchased domains
python domain_rotation_cli.py list
```

### Python API workflow

```python
from domain_manager import DomainRotationManager, create_domain_api_client

client = create_domain_api_client(
    "porkbun",
    api_key="pk1_...",
    api_secret="sk1_...",
)
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
print(candidate)

new_domain = manager.rotate_domain()
print(f"Active domain: {new_domain}")
```

## Registrar Configuration

### Porkbun

Required settings:

- `api_key`
- `api_secret`

Factory example:

```python
client = create_domain_api_client(
    "porkbun",
    api_key="pk1_...",
    api_secret="sk1_...",
)
```

### Namecheap

Required settings:

- `api_key`
- `username`
- `client_ip` (must be allowlisted in Namecheap API settings)

Optional settings:

- `api_user`
- `sandbox` (boolean)

Factory example:

```python
client = create_domain_api_client(
    "namecheap",
    api_key="nc_key",
    username="nc_user",
    client_ip="1.2.3.4",
    sandbox=True,
)
```

## Budget Management

`DomainRotationManager` enforces a monthly spending cap before purchases:

```python
status = manager.get_budget_status()
print(status["monthly_budget"])
print(status["current_spending"])
print(status["remaining"])
```

If a purchase would exceed the budget, it is denied.

## State Persistence

The CLI persists state in:

`~/.opsechat/domain_config.json`

Persisted state includes:

- active registrar
- monthly budget
- current spending
- owned domains
- active domain

Domain timestamps are serialized as ISO 8601 and reloaded safely on startup.

## DNS and Email Notes

Domain purchases do not automatically configure DNS records.
After rotation, configure MX/A records in your registrar dashboard and update
your mail infrastructure to use the new active domain.

## Testing

Run unit tests for domain manager logic:

```bash
python -m pytest tests/test_domain_manager.py
```

## Security Practices

- Never commit API keys or secrets.
- Use separate API credentials for test and production accounts.
- Keep domain budgets conservative to limit billing impact.
- Prefer registrar API keys scoped to minimum required privileges.
