# Domain Rotation Guide

## Overview

`domain_manager.py` now supports:

- Multi-provider registrar setup
- Provider-aware domain search and purchase
- Structured rotation responses (`rotate_to_new_domain`)
- Backward-compatible APIs (`rotate_domain`, `set_api_client`)

Current providers:

- Porkbun (JSON API)
- Namecheap (XML API)

## Quick Start (Python API)

### 1) Porkbun-only setup

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=25.0)
manager.configure(
    provider="porkbun",
    api_key="pk1_...",
    secret_key="sk1_...",
)

result = manager.rotate_to_new_domain(max_price=5.0)
print(result)
# {'success': True, 'domain': 'abcd1234.xyz', 'cost': 1.99, 'provider': 'porkbun', ...}
```

### 2) Multi-provider setup with fallback

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient, NamecheapAPIClient

manager = DomainRotationManager(monthly_budget=50.0)

manager.add_api_client("porkbun", PorkbunAPIClient("pk1_...", "sk1_..."))
manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(
        api_user="your-namecheap-user",
        api_key="your-namecheap-api-key",
        username="your-namecheap-user",
        client_ip="YOUR_WHITELISTED_IP",
        use_sandbox=True,  # set False for production
    ),
)

manager.set_active_provider("namecheap")

candidate = manager.find_cheap_available_domain(max_price=3.0)
print(candidate)
# {'domain': 'k3s9mx2r.xyz', 'price': 2.49, 'provider': 'namecheap', ...}
```

## Key APIs

### Search candidates

```python
domains = manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=3.00,
    limit=5,
)
```

### Rotate domain (structured result)

```python
result = manager.rotate_to_new_domain(max_price=5.0)
if result["success"]:
    print("Active domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

### Legacy rotate call

```python
new_domain = manager.rotate_domain()  # returns domain string or None
```

### Budget status

```python
print(manager.get_budget_status())
```

## CLI Usage

Use `domain_rotation_cli.py` for interactive setup:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

CLI improvements included in this update:

- Active provider selection (`porkbun` / `namecheap`)
- Safe persistence of owned domain timestamps (JSON serialization fix)
- Provider-aware purchase flow

## Namecheap Purchase Requirements

Namecheap purchases require contact profile fields. If you instantiate `NamecheapAPIClient` without a contact profile, search still works, but purchase will return a safe failure result.

Required fields:

- `first_name`
- `last_name`
- `address1`
- `city`
- `state_province`
- `postal_code`
- `country`
- `phone`
- `email_address`

Example:

```python
contact_profile = {
    "first_name": "Alice",
    "last_name": "Example",
    "address1": "123 Main St",
    "city": "Austin",
    "state_province": "TX",
    "postal_code": "73301",
    "country": "US",
    "phone": "+1.5555550100",
    "email_address": "alice@example.com",
}
```

## Web Route Integration Notes

`email_security_routes.py` now uses structured rotation responses:

- Endpoint: `POST /<path>/email/domain/rotate`
- Success response: HTTP 200 + `{"success": true, ...}`
- Failure response: HTTP 400 + `{"success": false, "error": "..."}`

## Security Notes

- Never commit API credentials.
- Use environment variables or local config files with strict permissions.
- Keep registrar keys scoped to least privilege where possible.

## Current Limitations

- DNS configuration remains a stub (`configure_domain_dns`) and intentionally returns structured "not implemented yet" data.
- Namecheap pricing and purchase responses are normalized, but endpoint payload details can vary by account settings and TLD.

