# Domain Rotation Guide

## Overview

OpSecChat supports burner-domain rotation through a registrar API client.
Current implementation includes:

- `PorkbunAPIClient` for domain search/purchase/pricing
- `DomainRotationManager` for budget-aware rotation logic
- `domain_rotation_cli.py` for operator workflows

The manager enforces a monthly budget and tracks owned domains in-memory.
The CLI persists state to a local config file so rotation history survives restarts.

## CLI Workflow

Use the CLI from the repository root:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Helpful Options

```bash
# Search with tighter budget constraints
python domain_rotation_cli.py search --max-price 2.50 --attempts 10

# Rotate non-interactively (automation/cron use)
python domain_rotation_cli.py rotate --max-price 3.00 --yes
```

## Configuration File

The CLI stores config in:

```text
~/.opsechat/domain_config.json
```

File permissions are set to `0600` on save.

Saved state includes:

- API credentials
- monthly budget
- current spending
- active domain
- owned domain history

Datetime fields are stored in ISO-8601 format and loaded back safely.

## Python API Usage

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="...", api_secret="...")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

result = manager.rotate_domain_result(max_price=3.0)
if result["success"]:
    print("New active domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

## Security Notes

- Keep API credentials out of git and shell history.
- Prefer environment injection or the CLI config prompt.
- Domain purchases are real billing events; always set a budget cap.

## Troubleshooting

### "API credentials not configured"

Run:

```bash
python domain_rotation_cli.py config
```

### "Could not find available cheap domain"

Increase attempts or price ceiling:

```bash
python domain_rotation_cli.py search --attempts 20 --max-price 5.00
```

### Budget exceeded

Increase monthly budget in config or reduce `--max-price`.
