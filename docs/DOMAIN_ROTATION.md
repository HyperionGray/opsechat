# Domain Rotation Guide

## Overview

OpSecChat supports burner-email domain rotation via registrar APIs. Current implementation includes:

- `domain_manager.py` for domain search/purchase/rotation logic
- `domain_rotation_cli.py` for interactive operations and local state persistence
- `rotate-domain.py` for flag-based scripting and automation

Supported registrar client today:

- Porkbun (`PorkbunAPIClient`)

## Prerequisites

1. Porkbun account with API access enabled
2. API key + secret key from Porkbun account settings
3. Python environment with project dependencies installed

## Configure Credentials

Run the interactive configuration command:

```bash
python domain_rotation_cli.py config
```

This stores credentials and local state at:

```text
~/.opsechat/domain_config.json
```

Permissions are set to `0600` when saved.

## Quick Command Reference

### Interactive CLI

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Flag-Based CLI (`rotate-domain.py`)

```bash
# Check one specific domain
python rotate-domain.py --search example.xyz

# Buy one specific domain
python rotate-domain.py --buy example.xyz --years 1

# Skip purchase confirmation (automation use)
python rotate-domain.py --buy example.xyz --years 1 --yes

# View locally tracked owned domains
python rotate-domain.py --list-owned

# Registrar pricing lookup
python rotate-domain.py --get-pricing xyz

# Show budget/domain status
python rotate-domain.py --status
```

## Programmatic Usage

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("your_api_key", "your_secret")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
if candidate:
    ok = manager.purchase_domain_if_budget_allows(
        candidate["domain"],
        candidate["price"],
    )
    print("Purchased:", ok)

print(manager.get_budget_status())
print("Active:", manager.get_active_domain())
```

## Budget and Rotation Behavior

- Purchases are blocked when monthly budget would be exceeded.
- Rotation searches low-cost TLDs and attempts purchase.
- Successfully purchased domains are tracked in local state.
- State persistence now serializes/restores datetime fields safely.

## Example Cron Job

Rotate periodically using the interactive CLI command:

```bash
0 2 * * 0 cd /path/to/opsechat && python domain_rotation_cli.py rotate
```

## Troubleshooting

### Credentials not configured

If commands fail with credential errors, run:

```bash
python domain_rotation_cli.py config
```

### Budget exceeded

Increase budget in config, or reduce target domain cost.

### Domain unavailable

Try a different domain or run random search/rotation commands.
