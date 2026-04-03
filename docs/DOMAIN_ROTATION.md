# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems using
`domain_manager.py` and `domain_rotation_cli.py`.

Current implementation supports:
- Porkbun (full search + purchase)
- Namecheap (search + purchase when contact profile is configured)
- Multiple registrar priority with fallback

## Supported Manager APIs

`DomainRotationManager` exposes:

- `configure(...)`
- `get_config()`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `search_cheap_domains(max_price=5.0, limit=5)`
- `purchase_domain_if_budget_allows(domain, price, registrar=None)`
- `rotate_domain()` (returns active domain string or `None`)
- `rotate_to_new_domain()` (returns structured result dict)
- `get_budget_status()`
- `get_owned_domains()`

## Registrar Priority and Fallback

The manager keeps a registrar priority list:

1. Try primary registrar first
2. Fall back to secondary registrar when purchase is unavailable/fails
3. Track which registrar completed the purchase

This allows gradual rollout of Namecheap while retaining Porkbun as fallback.

## CLI Usage

Configure credentials:

```bash
python domain_rotation_cli.py config
```

Show status:

```bash
python domain_rotation_cli.py status
```

Search cheap domains:

```bash
python domain_rotation_cli.py search
```

Rotate to a new domain:

```bash
python domain_rotation_cli.py rotate
```

List owned domains:

```bash
python domain_rotation_cli.py list
```

## Python Usage Examples

### Configure Porkbun

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=50.0)
manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
    monthly_budget=50.0,
    registrar="porkbun",
)
```

### Configure Namecheap with fallback

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=50.0)

# Primary Namecheap
manager.configure(
    api_key="nc_key",
    registrar="namecheap",
    username="nc_user",
    client_ip="1.2.3.4",
    sandbox=False,
    make_primary=True,
)

# Fallback Porkbun
manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
    registrar="porkbun",
    make_primary=False,
)
```

### Rotate and inspect result

```python
result = manager.rotate_to_new_domain()
if result["success"]:
    print(result["domain"], result["registrar"], result["cost"])
else:
    print(result["error"])
```

## Namecheap Notes

Namecheap purchase requires a complete contact profile in `contact_profile`.
If contact data is missing, Namecheap stays in lookup-only mode and fallback
registrars can complete purchases.

## Security Notes

- Do not commit API keys to source control.
- Store secrets in deployment environment variables or secure secret stores.
- Budget limits are enforced before purchase attempts.
