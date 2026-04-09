# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation manager and CLI for burner email domain operations.
The current implementation supports:

- Porkbun registrar API integration
- Budget-aware purchase checks
- Local state persistence (owned domains, active domain, spending)
- Expired cached-domain pruning

This guide documents the currently shipped commands and Python API.

## Supported Registrar

- Porkbun (implemented)

Additional registrars can be added by subclassing `DomainAPIClient`.

## CLI Setup

### 1) Configure credentials

```bash
python domain_rotation_cli.py config
```

You will be prompted for:

- Porkbun API key
- Porkbun API secret
- Monthly budget (USD)

Configuration is stored at:

`~/.opsechat/domain_config.json`

The file is written with mode `0600`.

### 2) Confirm status

```bash
python domain_rotation_cli.py status
```

## CLI Commands

```bash
python domain_rotation_cli.py config   # Set API credentials and budget
python domain_rotation_cli.py status   # Show active domain + budget summary
python domain_rotation_cli.py search   # Probe for cheap available candidates
python domain_rotation_cli.py rotate   # Purchase and activate a new domain
python domain_rotation_cli.py list     # Show locally tracked owned domains
python domain_rotation_cli.py prune    # Remove expired cached domains
```

## Persistence Model

The CLI persists these values in `~/.opsechat/domain_config.json`:

- `current_spending`
- `active_domain`
- `owned_domains`

Owned-domain timestamps are serialized as ISO 8601 strings and restored to
runtime datetime objects when loading the manager state.

## Python API (Current)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("your_api_key", "your_secret")
manager = DomainRotationManager(api_client=client, monthly_budget=25.0)

# Find a candidate under $5
candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
print(candidate)

# Purchase with budget guard
if candidate:
    result = manager.purchase_domain_if_budget_allows(
        candidate["domain"],
        candidate["price"],
    )
    print(result)

# Rotate (find + purchase)
rotation = manager.rotate_domain()
print(rotation)

# Export/import persisted state
state = manager.export_state()
manager.load_state(state)

# Prune expired local cached entries
pruned = manager.prune_expired_domains()
print(pruned)
```

## Rotation Automation

For non-interactive automation, use Python directly (the CLI `rotate` command
asks for purchase confirmation).

Example cron entry (weekly):

```bash
0 2 * * 0 cd /path/to/opsechat && python3 -c "from domain_manager import domain_rotation_manager; print(domain_rotation_manager.rotate_domain())"
```

If you persist manager state externally, run prune before rotation:

```python
from domain_manager import domain_rotation_manager

print(domain_rotation_manager.prune_expired_domains())
print(domain_rotation_manager.rotate_domain())
```

## Troubleshooting

### API request failures

- Verify Porkbun API credentials.
- Confirm outbound network access to `https://porkbun.com/api/json/v3`.

### Budget exceeded

- Check `status` output for current spending and remaining budget.
- Increase budget via `config` if needed.

### Invalid/unknown prices from registrar

The manager skips candidates with unparseable prices rather than crashing.
Retry search/rotate to fetch a new candidate.
