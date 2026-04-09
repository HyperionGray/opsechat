# Domain Rotation Guide

## Overview

Opsechat can rotate burner-email domains through a registrar API. The current production implementation supports Porkbun and exposes rotation through both web routes and `domain_rotation_cli.py`.

## Supported Registrar

- **Porkbun** (implemented)
- Additional registrars can be added by subclassing `DomainAPIClient` in `domain_manager.py`

## Setup

### 1. Create Porkbun API credentials

1. Sign in to [porkbun.com](https://porkbun.com)
2. Go to **Account -> API Access**
3. Create an API key pair and keep both values:
   - API Key
   - Secret API Key

### 2. Configure Opsechat

Use either the web UI or CLI.

#### Web UI

1. Open `/<secret-path>/email/config`
2. Submit:
   - API key
   - API secret
   - monthly budget (USD)
3. Save configuration

#### CLI

```bash
python domain_rotation_cli.py config
```

Configuration is saved to:

`~/.opsechat/domain_config.json`

The CLI stores registrar credentials and a persisted manager state (active domain, owned domains, spending, and budget).

## CLI Commands

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

- `status`: budget + active domain summary
- `search`: probe for low-cost available domains
- `rotate`: find and purchase a low-cost domain, then mark it active
- `list`: show owned domains with purchase/expiry metadata

## Python API (current implementation)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="pk1_xxx", api_secret="sk1_xxx")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

# Find one cheap candidate.
candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)

if candidate:
    result = manager.purchase_domain_if_budget_allows(
        candidate["domain"],
        candidate["price"],
    )
    print(result)

# One-shot search + purchase flow.
rotation_result = manager.rotate_domain()
print(rotation_result)

# Budget/spending information.
print(manager.get_budget_status())
```

## Budget Controls

Budget enforcement is built in:

- purchases are denied when `current_spending + price > monthly_budget`
- every successful purchase increments `current_spending`
- `get_budget_status()` returns:
  - `monthly_budget`
  - `current_spending`
  - `remaining`
  - `domains_owned`

## Persistence Behavior

The CLI now persists manager state using JSON-safe values:

- datetimes are saved in ISO-8601 format
- state is loaded on startup and converted back when possible
- legacy flat keys (`current_spending`, `owned_domains`, `active_domain`) are still accepted during migration

## Security Notes

- Do not commit registrar credentials
- Use dedicated registrar API keys with limited scope where available
- Rotate keys periodically

## Troubleshooting

### "No API client configured"

Set credentials first via:

```bash
python domain_rotation_cli.py config
```

or the web config page.

### "Budget exceeded"

Increase monthly budget in config or wait for your operational reset policy before purchasing more domains.

### "Could not find available cheap domain"

Retry later or raise `max_price`/`max_attempts` in direct API usage.
