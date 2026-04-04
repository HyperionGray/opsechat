# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows. The current implementation supports:

- Porkbun API
- Namecheap XML API
- Multi-provider fallback during availability search
- Budget-aware purchasing

## Supported Registrars

- `porkbun` (default)
- `namecheap` (requires API user + whitelisted client IP)

## CLI Quick Start

```bash
# Interactive configuration
python domain_rotation_cli.py config

# Search candidate domains
python domain_rotation_cli.py search

# Purchase + rotate active domain
python domain_rotation_cli.py rotate

# Inspect status and budget
python domain_rotation_cli.py status

# List owned domains
python domain_rotation_cli.py list
```

## Configuration Fields

### Porkbun

- API key
- API secret
- Monthly budget

### Namecheap

- API user
- API key
- Optional username (defaults to API user)
- Client IP (must be API-whitelisted)
- Optional sandbox mode
- Monthly budget

## Python API Usage

### Configure a single provider

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=50.0)
manager.configure(
    provider="porkbun",
    api_key="pk_live_xxx",
    secret_key="sk_live_xxx",
    monthly_budget=50.0,
)
```

### Configure multiple providers with fallback

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient, NamecheapAPIClient

manager = DomainRotationManager(monthly_budget=50.0)
manager.add_api_client("porkbun", PorkbunAPIClient("pk_live_xxx", "sk_live_xxx"))
manager.add_api_client("namecheap", NamecheapAPIClient(
    api_user="your_api_user",
    api_key="your_namecheap_key",
    client_ip="203.0.113.7",
))
manager.set_primary_provider("porkbun")

candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
print(candidate)
```

### Rotate with structured result

```python
result = manager.rotate_domain(return_details=True)
if result["success"]:
    print("New active domain:", result["domain"])
    print("Provider used:", result["provider"])
    print("Budget:", result["budget_status"])
else:
    print("Rotation failed:", result["error"])
```

## Budget Behavior

- Purchases that exceed `monthly_budget` are denied.
- Spending is tracked in `current_spending`.
- Summary is available via `get_budget_status()`.

## Security Notes

- Never commit API credentials.
- Prefer environment injection or runtime-only config files.
- Namecheap purchases require complete contact information in `registrant_contact`.
- Use sandbox credentials for testing purchase flows.

## Troubleshooting

### Rotation returns no domain

- Increase attempts (`max_attempts`)
- Increase price cap (`max_price`)
- Verify API credentials
- Verify provider has network/API access

### Namecheap purchase fails with missing fields

Provide required registrant contact fields (`FirstName`, `LastName`, `Address1`, `City`, `StateProvince`, `PostalCode`, `Country`, `Phone`, `EmailAddress`) when constructing `NamecheapAPIClient`.
