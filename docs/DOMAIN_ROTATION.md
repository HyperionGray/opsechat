# Domain Rotation Guide

## Overview

OpSecChat includes a domain-rotation manager and CLI for burner email domains.
The flow is:

1. Configure Porkbun API credentials.
2. Search for cheap available domains.
3. Purchase/rotate within a monthly budget.
4. Persist local state safely between runs.
5. Prune stale/expired state entries when needed.

## CLI Quick Start

```bash
# 1) Configure credentials and budget
python domain_rotation_cli.py config

# 2) Check current state
python domain_rotation_cli.py status

# 3) Search for cheap candidates
python domain_rotation_cli.py search

# 4) Purchase + activate a new domain
python domain_rotation_cli.py rotate

# 5) List all stored domains
python domain_rotation_cli.py list

# 6) Clean up expired/invalid stored entries
python domain_rotation_cli.py prune
```

## What Is Persisted

Configuration file: `~/.opsechat/domain_config.json`

- API credentials (`api_key`, `api_secret`)
- `monthly_budget`
- Runtime state:
  - `current_spending`
  - `active_domain`
  - `owned_domains` (with normalized ISO timestamps)

State loading is resilient to legacy data where timestamps are strings.

## Python API (Current)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="...", api_secret="...")
manager = DomainRotationManager(api_client=client, monthly_budget=10.0)

# Search for one cheap available domain
candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)

# Purchase if budget allows
if candidate:
    manager.purchase_domain_if_budget_allows(candidate["domain"], candidate["price"])

# Rotate using built-in search + purchase flow
new_active = manager.rotate_domain()

# Clean stale records
removed_count = manager.cleanup_expired_domains()
print("Removed:", removed_count)

# Save/load state
saved = manager.export_state()
manager.load_state(saved)
```

## Budget Behavior

- Purchase is blocked if `current_spending + price > monthly_budget`.
- Spending and domain ownership are tracked in memory and can be exported.

## Troubleshooting

### `list` fails with datetime errors

Upgrade to the current CLI and run:

```bash
python domain_rotation_cli.py prune
```

This removes malformed/expired entries and normalizes remaining state.

### Could not find cheap domains

- Increase `max_attempts` or budget.
- Retry later; registrar availability and pricing vary.

### Purchase failed

- Verify API key/secret from Porkbun account API settings.
- Ensure available account balance and budget headroom.

