# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows.
The current implementation is in `domain_manager.py` and includes:

- multi-registrar support through an abstract `DomainAPIClient`
- provider fallback during domain search/rotation
- monthly budget enforcement
- safe state export/import for persisted CLI config

## Supported Registrars

### 1. Porkbun

- API style: JSON
- Best for: low-cost random TLD rotation
- Notes: full search/purchase/pricing support

### 2. Namecheap

- API style: XML
- Best for: provider redundancy and fallback
- Notes:
  - search and pricing are supported
  - purchases require contact details configured in the Namecheap client
  - client supports sandbox endpoint mode

## Core API Surface

`DomainRotationManager` now exposes the following stable methods:

```python
manager.configure(...)
manager.get_config()
manager.find_cheap_available_domain(...)
manager.purchase_domain_if_budget_allows(...)
manager.rotate_to_new_domain(...)
manager.rotate_domain(...)  # backward-compatible string return
manager.export_state()
manager.import_state(...)
```

## Quick Start (Python)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

porkbun = PorkbunAPIClient("pk_live_xxx", "sk_live_xxx")
manager = DomainRotationManager(api_client=porkbun, monthly_budget=25.0)

result = manager.rotate_to_new_domain(max_price=5.0)
if result["success"]:
    print(result["domain"], result["provider"], result["price"])
else:
    print(result["error"])
```

## Multi-Provider Setup Example

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient, NamecheapAPIClient

manager = DomainRotationManager(monthly_budget=40.0)
manager.add_api_client(
    "porkbun",
    PorkbunAPIClient("pk_live_xxx", "sk_live_xxx"),
    set_primary=True,
)

manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(
        api_user="namecheap_user",
        api_key="namecheap_key",
        username="namecheap_user",
        client_ip="127.0.0.1",
        sandbox=True,
        default_contacts={
            "FirstName": "Ops",
            "LastName": "Team",
            "Address1": "123 Example St",
            "City": "Example City",
            "StateProvince": "CA",
            "PostalCode": "94105",
            "Country": "US",
            "Phone": "+1.5555555555",
            "EmailAddress": "ops@example.com",
        },
    ),
    set_primary=False,
)

rotation = manager.rotate_to_new_domain(max_price=4.0)
print(rotation)
```

If the primary provider does not return an available cheap domain, the manager
automatically tries the next configured provider.

## CLI Usage

The local helper is `domain_rotation_cli.py`:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

The CLI persists manager state using:

- `DomainRotationManager.export_state()`
- `DomainRotationManager.import_state()`

This preserves timestamps for purchased/expiry metadata while keeping JSON
serialization safe.

## Budget Controls

Budget checks are enforced before purchase:

- if `current_spending + price > monthly_budget`, purchase is denied
- all successful purchases are recorded in `owned_domains`
- each record includes `provider`, `purchased_at`, and `expires_at`

Inspect current values with:

```python
status = manager.get_budget_status()
print(status)
```

## Web Route Integration

Email configuration/rotation routes can rely on:

- `domain_rotation_manager.configure(...)`
- `domain_rotation_manager.get_config()`
- `domain_rotation_manager.rotate_domain()`

This keeps older route code working while enabling multi-provider internals.

## Security Notes

- never commit registrar credentials
- use separate keys for production and testing
- prefer registrar account-level spending alerts
- use Namecheap sandbox mode when validating API connectivity

## Troubleshooting

### "No API client configured"

Configure at least one provider before calling search/rotate.

### "Purchase failed or budget exceeded"

Inspect:

- `monthly_budget`
- `current_spending`
- provider credentials
- provider-specific purchase requirements (Namecheap contact fields)

### Namecheap search works but purchase fails

Set `default_contacts` on `NamecheapAPIClient` with required contact fields.
