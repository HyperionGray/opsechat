# Domain Rotation Guide

## Overview

OpSecChat can rotate burner-email domains using registrar APIs. The implementation lives in `domain_manager.py` and supports:

- `PorkbunAPIClient`
- `NamecheapAPIClient`
- `DomainRotationManager` with registrar fallback

`DomainRotationManager` attempts the preferred registrar first, then any additional configured registrars if search or purchase fails.

## Current Python API

```python
from domain_manager import (
    DomainRotationManager,
    PorkbunAPIClient,
    NamecheapAPIClient,
)
```

### 1) Configure a preferred registrar

```python
manager = DomainRotationManager(monthly_budget=20.0)
manager.set_api_client(
    PorkbunAPIClient(api_key="pk...", api_secret="sk..."),
    name="porkbun",
    preferred=True,
)
```

### 2) Add fallback registrar(s)

```python
manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(
        api_key="namecheap-api-key",
        username="namecheap-user",
        client_ip="203.0.113.10",
    ),
    preferred=False,
)
```

### 3) Search and rotate

```python
candidate = manager.find_cheap_available_domain(max_price=5.0)
if candidate:
    # candidate includes: domain, price, tld, registrar
    print(candidate)

new_domain = manager.rotate_domain()
print("Active domain:", new_domain)
```

## Budget and state

```python
status = manager.get_budget_status()
print(status)
```

Returned fields include:

- `monthly_budget`
- `current_spending`
- `remaining`
- `domains_owned`
- `preferred_registrar`
- `configured_registrars`

## Web route compatibility helpers

`DomainRotationManager` now includes:

- `configure(...)`
- `get_config()`

These methods support existing route wiring in `email_security_routes.py`.

## CLI usage

Use `domain_rotation_cli.py`:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

The `config` command now supports selecting `porkbun` or `namecheap`.

## Notes on Namecheap purchasing

Namecheap purchases require complete contact profile fields. If these are missing, purchase calls fail safely with a validation message.

Availability and pricing fallback are still useful even when purchases are disabled or incomplete.
