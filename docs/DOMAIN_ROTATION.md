# Domain Rotation Guide

## Overview

OpSecChat can rotate burner-email domains using a registrar API (currently Porkbun).
The rotation manager now supports:

- In-memory API configuration from the web UI
- Budget-aware domain purchases
- Structured rotation results for API/UI flows
- Safe parsing of registrar price formats (for example: `"$2.49 USD"`)

## Configure from the Web UI

1. Open:
   - `/<secret-path>/email/config`
2. In **Domain API (Porkbun) - Burner Email Domains**:
   - Enter API key
   - Enter API secret
   - Set monthly budget
3. Submit **Configure Domain API**

After configuration, use **Rotate to New Domain** to purchase and activate a new burner domain.

## Domain Manager API (Python)

```python
from domain_manager import domain_rotation_manager

# Configure Porkbun access and budget
domain_rotation_manager.configure(
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=25.0,
)

# Find an available low-cost domain
candidate = domain_rotation_manager.find_cheap_available_domain(
    max_price=5.0,
    max_attempts=10,
    tlds=["xyz", "club", "online"],
)

# Rotate with structured result payload
result = domain_rotation_manager.rotate_domain_with_result()
print(result["success"], result.get("domain"), result.get("error"))
```

### Configuration Snapshot

`get_config()` returns a redacted snapshot suitable for templates/logging:

```python
{
  "configured": True,
  "provider": "porkbun",
  "api_key_masked": "******1234",
  "secret_key_configured": True,
  "monthly_budget": 25.0,
  "current_spending": 1.99,
  "active_domain": "abc123.xyz",
  "domains_owned": 1
}
```

## CLI Usage

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### State Persistence

The CLI stores state in `~/.opsechat/domain_config.json`.
Owned-domain timestamps are now serialized safely (ISO timestamps) and restored on load.

## Budget Behavior

- Purchases are blocked if the next purchase would exceed the configured monthly budget.
- `get_budget_status()` returns:
  - `monthly_budget`
  - `current_spending`
  - `remaining`
  - `domains_owned`

## Security Notes

- Keep API keys out of git and shell history.
- Prefer environment or interactive prompt input for secrets.
- Credentials shown in UI/config snapshots are masked.
