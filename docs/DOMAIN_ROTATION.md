# Domain Rotation Guide

## Overview

OpSecChat includes domain rotation support for burner email workflows.

Current implementation goals:
- Keep domain purchases under a monthly budget
- Prefer low-cost random domains on cheap TLDs
- Support multiple registrar providers with failover
- Persist CLI state safely between runs

## Supported Registrars

- Porkbun (`PorkbunAPIClient`)
- Namecheap (`NamecheapAPIClient`)

`DomainRotationManager` can register more than one provider and will:
1. Try the active provider first
2. Fall back to other configured providers when searching/purchasing
3. Track which provider successfully purchased each domain

## Python API

### Basic usage (single provider)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

manager = DomainRotationManager(monthly_budget=20.0)
manager.add_api_client(
    "porkbun",
    PorkbunAPIClient(api_key="pk_live_xxx", api_secret="sk_live_xxx"),
    set_active=True,
)

new_domain = manager.rotate_domain()
print("new domain:", new_domain)
print("budget:", manager.get_budget_status())
```

### Multi-provider with failover

```python
from domain_manager import (
    DomainRotationManager,
    PorkbunAPIClient,
    NamecheapAPIClient,
)

manager = DomainRotationManager(monthly_budget=30.0)

manager.add_api_client(
    "porkbun",
    PorkbunAPIClient(api_key="pk_live_xxx", api_secret="sk_live_xxx"),
    set_active=True,
)

manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(
        api_key="nc_api_xxx",
        username="your-namecheap-username",
        client_ip="203.0.113.10",
        use_sandbox=False,
    ),
)

# Searches active provider first, then fallback providers.
domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=5)
print(domain_info)

# Force one provider when needed.
namecheap_domain = manager.rotate_domain(provider="namecheap")
print(namecheap_domain)
```

### Budget and provider status

```python
status = manager.get_budget_status()
print(status["monthly_budget"])
print(status["current_spending"])
print(status["remaining"])
print(status["domains_owned"])
print(status["active_provider"])
print(status["providers_configured"])
```

## CLI Usage (`domain_rotation_cli.py`)

Configure credentials:

```bash
python domain_rotation_cli.py config
```

Available commands:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### CLI state persistence

The CLI stores state at:

`~/.opsechat/domain_config.json`

Saved fields include:
- Current spending
- Owned domains
- Active domain
- Active provider

Timestamp fields (`purchased_at`, `expires_at`) are serialized as ISO-8601 strings
and restored to `datetime` objects on load.

## Namecheap Notes

Namecheap API requires:
- API key
- username (and optionally separate `api_user`)
- allowlisted client IP in Namecheap API settings

For purchase operations, Namecheap also requires contact fields. The client applies
sane defaults and supports overrides through `contact_profile`.

## Operational Tips

- Start with one primary registrar and one fallback registrar
- Keep a realistic monthly budget and monitor remaining spend
- Use `max_price` defensively for search/purchase workflows
- Test API credentials and IP allowlists before automation

## Troubleshooting

### No providers configured

Symptom:
- CLI exits with credential/configuration error

Fix:
- Run `python domain_rotation_cli.py config`
- Ensure at least one registrar has valid credentials

### Namecheap calls failing

Common causes:
- Client IP not allowlisted in Namecheap
- Wrong username/API key
- Sandbox/live mismatch

### Purchase fails despite search availability

Potential causes:
- Domain became unavailable between search and purchase
- Budget exceeded
- Registrar-specific requirements rejected request

Check:
- `domain_rotation_cli.py status`
- Application logs for provider-specific error messages
