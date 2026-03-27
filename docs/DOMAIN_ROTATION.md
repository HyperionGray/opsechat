# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows.  
The implementation currently uses:

- `domain_manager.py` for API client + domain rotation logic
- `domain_rotation_cli.py` for operational usage and automation

This guide reflects the current, runnable interfaces.

## Supported Registrar

- **Porkbun** (implemented)
- Additional registrars can be added by extending `DomainAPIClient`

## Setup

### 1) Get Porkbun API credentials

1. Sign up at [porkbun.com](https://porkbun.com)
2. Open Account -> API Access
3. Enable API access
4. Save:
   - API Key
   - Secret API Key

### 2) Configure credentials

#### Option A: CLI config (recommended)

```bash
python domain_rotation_cli.py config \
  --api-key "pk1_example" \
  --api-secret "sk1_example" \
  --monthly-budget 10 \
  --non-interactive
```

#### Option B: Environment variables

```bash
export PORKBUN_API_KEY="pk1_example"
export PORKBUN_SECRET_KEY="sk1_example"
export DOMAIN_BUDGET="10"
```

The CLI will use config file values first, then environment variables.

## CLI Usage

### Show status

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py status --json
```

### Search available cheap domains

```bash
python domain_rotation_cli.py search --attempts 5 --max-price 5.0
python domain_rotation_cli.py search --attempts 3 --max-price 2.5 --json
```

### Rotate to a new domain

```bash
# interactive confirmation
python domain_rotation_cli.py rotate --max-price 5.0

# automation-safe mode
python domain_rotation_cli.py rotate --yes --max-price 3.0 --json
```

### List owned domains

```bash
python domain_rotation_cli.py list
python domain_rotation_cli.py list --json
```

## Python API Usage

### Basic manager workflow

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("pk1_example", "sk1_example")
manager = DomainRotationManager(api_client=client, monthly_budget=10.0)

candidate = manager.find_cheap_available_domain(max_price=3.0, max_attempts=10)
if candidate:
    purchased = manager.purchase_domain_if_budget_allows(
        candidate["domain"], candidate["price"]
    )
    print("Purchased:", purchased, "Active:", manager.get_active_domain())
else:
    print("No suitable domain found.")
```

### Budget inspection

```python
status = manager.get_budget_status()
print(status["monthly_budget"], status["current_spending"], status["remaining"])
```

## Automation Example (cron)

Weekly automatic rotation with JSON output:

```bash
0 2 * * 0 cd /path/to/opsechat && \
python domain_rotation_cli.py rotate --yes --json >> /var/log/opsechat-domain-rotation.log 2>&1
```

## Notes on persisted state

The CLI stores operational state in:

- `~/.opsechat/domain_config.json`

Persisted fields include:

- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains` (with timestamp metadata)

## Security guidance

- Never commit API credentials.
- Prefer environment variables or protected local config.
- Keep `~/.opsechat/domain_config.json` file permissions restricted (the CLI sets mode `0600`).

## Troubleshooting

### Missing credentials

If you see credential errors:

1. Run `python domain_rotation_cli.py config` interactively, or
2. Set `PORKBUN_API_KEY` and `PORKBUN_SECRET_KEY`.

### Budget blocks purchase

Use:

```bash
python domain_rotation_cli.py status --json
```

Then increase budget:

```bash
python domain_rotation_cli.py config --monthly-budget 20 --non-interactive
```
