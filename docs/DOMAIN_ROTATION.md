# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems.  
The current implementation supports **multiple registrars** with priority/fallback search:

- **Porkbun** (recommended default, simple API)
- **Namecheap** (newly integrated)

`DomainRotationManager` searches with the preferred registrar first, then falls back to other configured registrars if needed.

## Supported Registrars

### Porkbun

Requirements:
- API key
- Secret API key

### Namecheap

Requirements:
- API key
- Username
- Client IP (must be whitelisted in Namecheap API settings)
- Optional `ApiUser` (defaults to Username)

Notes:
- Domain creation via Namecheap requires registrant/contact profile fields.
- Availability + pricing checks work without purchase contact data.

## CLI Usage

The supported command interface is:

```bash
python domain_rotation_cli.py [-h] [--registrar {porkbun,namecheap}] \
  {config,status,search,rotate,list}
```

### Configure registrar credentials

```bash
python domain_rotation_cli.py config
```

This now supports selecting Porkbun or Namecheap and stores credentials under:

`~/.opsechat/domain_config.json`

Legacy config keys are auto-migrated to the new multi-registrar format.

### Check status

```bash
python domain_rotation_cli.py status
```

Shows:
- active domain
- budget usage
- preferred registrar
- configured registrars

### Search for cheap domains

```bash
# Preferred registrar with fallback
python domain_rotation_cli.py search

# Force only Namecheap for this command
python domain_rotation_cli.py search --registrar namecheap
```

### Rotate domain

```bash
# Preferred registrar with fallback search
python domain_rotation_cli.py rotate

# Force registrar override
python domain_rotation_cli.py rotate --registrar porkbun
```

### List owned domains

```bash
python domain_rotation_cli.py list
```

The list output includes the registrar for each purchased domain.

## Runtime API Usage

### Configure manager with multiple clients

```python
from domain_manager import (
    DomainRotationManager,
    PorkbunAPIClient,
    NamecheapAPIClient,
)

manager = DomainRotationManager(monthly_budget=50.0)
manager.add_api_client("porkbun", PorkbunAPIClient("pk1_x", "sk1_y"))
manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(
        api_key="nc_key",
        username="nc_user",
        client_ip="203.0.113.10",
    ),
)
manager.set_preferred_registrar("porkbun")
```

### Search + purchase flow

```python
domain_info = manager.find_cheap_available_domain(max_price=5.0)
if domain_info:
    ok = manager.purchase_domain_if_budget_allows(
        domain_info["domain"],
        domain_info["price"],
        registrar=domain_info["registrar"],
    )
```

## Budget and Safety

- Monthly budget is enforced before purchase.
- Purchase data is tracked in `owned_domains` with:
  - domain
  - price
  - registrar
  - purchase timestamp
  - expiry timestamp

## Troubleshooting

### "No valid registrar credentials configured"

Run:

```bash
python domain_rotation_cli.py config
```

and ensure at least one registrar has complete required fields.

### Namecheap search fails

Validate:
- API is enabled on your account
- Client IP is whitelisted
- Username/API key are correct

### Namecheap purchase fails with missing fields

Provide required contact profile fields when constructing `NamecheapAPIClient` for purchase workflows.

## Cleanup Notes

This guide was updated to match actual production code paths and remove stale references to non-existent APIs (for example `rotate_to_new_domain`, `budget_manager`, and `set_test_mode`).
