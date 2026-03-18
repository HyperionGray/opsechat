# Domain Rotation Guide

## Overview

OpSecChat supports automated burner-domain rotation with budget controls and
multiple registrar providers.

## Supported Registrars

| Registrar | Status | Notes |
| --- | --- | --- |
| Porkbun | Supported | Recommended for low-cost promotional TLDs |
| Namecheap | Supported | Search/pricing supported; purchases require full contact profile |

## CLI Setup

Use the CLI to configure credentials and rotate domains:

```bash
python domain_rotation_cli.py config
```

The CLI stores config at:

```text
~/.opsechat/domain_config.json
```

### Porkbun Configuration

During `config`, choose `porkbun` and provide:

- API key
- API secret
- monthly budget

### Namecheap Configuration

During `config`, choose `namecheap` and provide:

- username
- API user (or use username)
- API key
- client IP (required by Namecheap API)
- monthly budget

## CLI Commands

```bash
python domain_rotation_cli.py status   # show provider/budget/domain status
python domain_rotation_cli.py search   # search for cheap candidate domains
python domain_rotation_cli.py rotate   # search and purchase one domain
python domain_rotation_cli.py list     # list purchased domains
```

Purchases and active-domain metadata are persisted in the config file. Timestamps
are stored as ISO-8601 strings so state survives restarts cleanly.

## Python API Usage

### Single Provider

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

manager = DomainRotationManager(monthly_budget=25.0)
manager.add_api_client("porkbun", PorkbunAPIClient("pk...", "sk..."), make_active=True)

new_domain = manager.rotate_domain()
print(new_domain)
```

### Multi-Provider Fallback

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient, NamecheapAPIClient

manager = DomainRotationManager(monthly_budget=25.0)
manager.add_api_client("porkbun", PorkbunAPIClient("pk...", "sk..."), make_active=True)
manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(api_key="nc_key", username="nc_user", client_ip="1.2.3.4"),
)

result = manager.find_cheap_available_domain(max_price=5.0)
print(result)  # includes provider field
```

### Structured Rotation Result

```python
details = manager.rotate_domain_with_details()
if details["success"]:
    print(f"Rotated to {details['domain']} via {details['provider']}")
else:
    print(details["error"])
```

## Budget and Safety Notes

- Purchases are blocked when monthly budget would be exceeded.
- Domain history records provider, price, purchase time, and expiry time.
- Never commit API keys or secret keys to git.
- Use dedicated low-privilege API keys for production.
