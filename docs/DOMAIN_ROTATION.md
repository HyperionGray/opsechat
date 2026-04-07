# Domain Rotation Guide

## Overview

OpSecChat supports automatic domain rotation for burner email workflows using a
Porkbun-backed domain manager (`domain_manager.py`) and a command-line helper
(`domain_rotation_cli.py`).

The implementation now includes:

- Typed domain API abstraction (`DomainAPIClient`)
- Porkbun integration (`PorkbunAPIClient`)
- Budget-aware rotation manager (`DomainRotationManager`)
- JSON-safe state export/import (`export_state` and `load_state`)
- Web UI integration at `/<path>/email/config`
- CLI persistence in `~/.opsechat/domain_config.json`

## Supported Registrars

Currently implemented:

- **Porkbun** (default and recommended)

Future registrars can be added by implementing `DomainAPIClient`.

## Setup

### 1. Get Porkbun API Credentials

1. Sign up at [porkbun.com](https://porkbun.com)
2. Go to **Account -> API Access**
3. Create API credentials and save:
   - API Key
   - Secret API Key

### 2. Configure in OpSecChat (Web UI)

1. Open `http://your-onion-url/<secret-path>/email/config`
2. In **Domain API (Porkbun)**:
   - Enter API key
   - Enter API secret
   - Set monthly budget
3. Submit **Configure Domain API**

After configuration you can rotate domains from the same page using
**Rotate to New Domain**.

### 3. Configure via CLI

```bash
python domain_rotation_cli.py config
```

Then use:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Domain Manager API (Implemented)

The manager API currently implemented in `domain_manager.py`:

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
manager.configure(api_key="pk1_...", secret_key="sk1_...", monthly_budget=20.0)

config = manager.get_config()  # returns masked keys by default
budget = manager.get_budget_status()

result = manager.rotate_domain_with_result()
if result["success"]:
    print(result["domain"], result["price"])
```

Key methods:

- `configure(api_key, secret_key, monthly_budget)`
- `get_config(mask_secrets=True)`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_domain()` (returns `str | None`)
- `rotate_domain_with_result()` (returns structured dict)
- `export_state()` / `load_state()`

## State Persistence

`DomainRotationManager` stores domain history in memory as Python objects
(including `datetime` values). For persistence, use:

- `export_state()` to convert to JSON-safe payloads (ISO timestamps)
- `load_state()` to hydrate persisted payloads back into typed state

This is used by `domain_rotation_cli.py` to prevent serialization errors and to
restore values that can be rendered safely in CLI output.

## Budget Controls

The manager enforces:

- Monthly spending cap
- Per-purchase budget validation
- Running spending total
- Active domain tracking

You can inspect budget data with:

```python
status = manager.get_budget_status()
print(status["monthly_budget"], status["current_spending"], status["remaining"])
```

## Security Notes

- Never commit API keys/secrets to version control
- Use dedicated registrar credentials for this service
- Rotate API credentials periodically
- Keep budgets conservative to reduce accidental spend

## Troubleshooting

### "No API client configured"

Configure credentials first with either:

- Web UI: `/<path>/email/config`
- CLI: `python domain_rotation_cli.py config`

### "Domain rotation failed"

Common causes:

- Invalid API credentials
- Budget exhausted
- Temporary registrar/network failure
- No cheap domains found within price threshold

### CLI list/status errors after restart

Make sure you are on the latest code path that uses manager
`export_state`/`load_state`; this resolves datetime JSON mismatch issues.
