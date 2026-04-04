# Domain Rotation Guide

## Overview

OpSecChat supports domain rotation for burner email workflows via:

- `domain_manager.py` (core API and budget logic)
- `domain_rotation_cli.py` (operator-facing CLI)

This guide documents the currently implemented behavior and commands.

## Supported Registrar

- **Porkbun** via `PorkbunAPIClient`

Other registrars can be added by implementing `DomainAPIClient`.

## Configure the CLI

Run:

```bash
python domain_rotation_cli.py config
```

The CLI stores configuration in:

```text
~/.opsechat/domain_config.json
```

Saved settings:

- API key + secret
- Monthly budget
- Preferred TLD list (comma-separated input, normalized)
- Max search price
- Persisted purchase state (owned domains, active domain, spending)

## Available Commands

```bash
python domain_rotation_cli.py config   # Configure credentials + policy
python domain_rotation_cli.py status   # Show active domain and budget status
python domain_rotation_cli.py search   # Probe for cheap available domains
python domain_rotation_cli.py rotate   # Search + purchase + activate new domain
python domain_rotation_cli.py list     # List persisted owned domains
```

## Search and Purchase Behavior

### TLD selection

By default, the manager searches:

- `xyz`
- `club`
- `online`
- `site`
- `website`

You can override this in `config`. Input like:

```text
.XYZ, club, online
```

is normalized to:

```text
xyz, club, online
```

### Price handling

The manager accepts numeric price formats from registrar responses, including:

- `2.99`
- `"2.99"`
- `"$2.99"`
- `"€2.99"`

Unparseable values (for example `"free"` or empty strings) are skipped safely.

### Budget guardrail

`purchase_domain_if_budget_allows()` blocks purchases that exceed monthly budget.

## Persistence and State Recovery

After successful purchases, the CLI persists:

- `current_spending`
- `owned_domains`
- `active_domain`

Owned-domain timestamps (`purchased_at`, `expires_at`) are serialized as ISO-8601 strings and parsed back on load. This keeps `list` stable across restarts and avoids datetime serialization/type crashes.

## Python API Example

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("API_KEY", "API_SECRET")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(
    max_price=3.0,
    max_attempts=10,
    tld_candidates=["xyz", "club"]
)

if candidate:
    ok = manager.purchase_domain_if_budget_allows(
        candidate["domain"],
        candidate["price"]
    )
    print("purchased:", ok, "active:", manager.get_active_domain())
```

## Troubleshooting

- **`Error: API credentials not configured`**
  - Run `python domain_rotation_cli.py config`.
- **No domains found**
  - Increase max search price, expand TLD list, or retry.
- **Budget exceeded**
  - Raise monthly budget or wait for your operational budget window reset.

