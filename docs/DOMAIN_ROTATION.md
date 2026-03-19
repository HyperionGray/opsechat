# Domain Rotation Guide

## Overview

`domain_manager.py` and `domain_rotation_cli.py` provide domain lifecycle management
for burner-email operations:

- search low-cost domains
- purchase within a monthly budget
- persist local domain state safely
- sync local state from registrar ownership
- clean up expired local domain records

Current registrar support: Porkbun API.

## CLI Commands

```bash
# Configure credentials and budget
python domain_rotation_cli.py config

# Show active domain + budget status
python domain_rotation_cli.py status

# Search for cheap available domains
python domain_rotation_cli.py search

# Purchase and activate a newly found domain
python domain_rotation_cli.py rotate

# List locally tracked domains
python domain_rotation_cli.py list

# Pull owned domains from registrar into local state
python domain_rotation_cli.py sync

# Remove expired local domain entries
python domain_rotation_cli.py cleanup
```

## Configuration

Configuration is stored at:

`~/.opsechat/domain_config.json`

Fields written by the CLI include:

- `api_key`
- `api_secret`
- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains`

## State Persistence

`DomainRotationManager` now exports and loads state directly:

- `export_state()` returns JSON-serializable data
- `load_state(state)` restores local state safely

Datetime fields (`purchased_at`, `expires_at`) are stored as ISO 8601 strings and
parsed back to `datetime` objects on load.

This avoids the prior failure mode where direct JSON serialization of raw
`datetime` objects caused save errors.

## Sync Behavior

`sync` calls `DomainRotationManager.sync_owned_domains()`:

- fetches domains from the registrar (`list_domains()`)
- adds missing domains into local tracked state
- avoids duplicate inserts
- sets an active domain if none is currently set

Synced entries are marked with:

```json
{
  "source": "remote_sync"
}
```

## Cleanup Behavior

`cleanup` calls `DomainRotationManager.cleanup_expired_domains()`:

- removes domains whose `expires_at` is in the past
- returns a summary with removed/remaining counts
- reassigns `active_domain` if the active domain was removed

## Python API

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient(api_key="...", api_secret="...")
manager = DomainRotationManager(api_client=client, monthly_budget=50.0)

status = manager.get_budget_status()
print(status)

# Find and purchase a domain
domain = manager.find_cheap_available_domain(max_price=5.0)
if domain:
    manager.purchase_domain_if_budget_allows(domain["domain"], domain["price"])

# Persist/restore
state = manager.export_state()
manager.load_state(state)

# Housekeeping
manager.sync_owned_domains()
manager.cleanup_expired_domains()
```

## Operational Notes

- Keep API credentials out of git and shell history where possible.
- Use low monthly budgets initially and raise only as needed.
- After `rotate`, configure DNS and mail routing for the new active domain.
- Run `sync` before `cleanup` if registrar and local state may have drifted.
