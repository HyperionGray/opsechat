# Domain Rotation Guide

## Overview

OpSecChat supports budget-aware burner-domain rotation using Porkbun. The
domain manager and CLIs now share one consistent implementation.

## What is Implemented

- `domain_manager.py`
  - `PorkbunAPIClient` for registrar API calls
  - `DomainRotationManager` for domain search, purchase, rotation, and budget tracking
  - Config compatibility helpers used by email routes:
    - `configure(...)`
    - `get_config()`
    - `rotate_domain(return_details=True)` for JSON API responses
  - Safe persistence helpers:
    - `export_state()` (JSON-safe)
    - `load_state(...)` (restores datetime fields)

- `domain_rotation_cli.py`
  - Configured interactive flow (`config`)
  - Search (`search`)
  - Rotation (`rotate`)
  - Status (`status`)
  - Owned domain listing (`list`)

- `rotate-domain.py` (compatibility wrapper)
  - Supports legacy docs/ops usage:
    - `--search`
    - `--buy`
    - `--years`
    - `--list-owned`
    - `--get-pricing`
    - `--status`

## Setup

1. Create API credentials at <https://porkbun.com/account/api>.
2. Configure with the maintained CLI:

```bash
python domain_rotation_cli.py config
```

Credentials are stored in `~/.opsechat/domain_config.json` with `0600` file
permissions.

## CLI Usage

### Maintained CLI

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Legacy-Compatible CLI

```bash
python rotate-domain.py --search example.xyz
python rotate-domain.py --buy example.xyz --years 1
python rotate-domain.py --list-owned
python rotate-domain.py --get-pricing xyz
python rotate-domain.py --status
```

## Python API Usage

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("pk1_xxx", "sk1_xxx")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

details = manager.rotate_domain(return_details=True)
if details["success"]:
    print("New active domain:", details["domain"])
else:
    print("Rotation failed:", details["error"])
```

## Budget and Persistence Notes

- Purchases are denied when projected spending exceeds monthly budget.
- Multi-year purchases are supported by `purchase_domain_if_budget_allows(..., years=N)`.
- Domain ownership entries are persisted with ISO datetime strings and restored safely.

## Security Notes

- Never commit API keys.
- Use a dedicated registrar sub-key with least privilege.
- Rotate keys periodically.

## Troubleshooting

### Missing credentials

Run:

```bash
python domain_rotation_cli.py config
```

### Budget exceeded

Increase budget in config or wait for next budget period.

### No cheap domain found

Search again (`search`) or raise max budget and retry.
