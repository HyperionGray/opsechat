# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows through
`domain_manager.py`. The current implementation uses Porkbun API credentials and
adds budget controls, structured rotation results, and state persistence helpers.

## What is implemented

- Porkbun API client (`PorkbunAPIClient`)
- Domain search for low-cost available domains
- Budget-aware domain purchasing
- Active-domain rotation workflow
- Test mode for simulated purchases (no real spend)
- Manager state export/import for CLI persistence

## Configure credentials and budget

### Python API

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_your_key",
    secret_key="sk1_your_secret",
    monthly_budget=25.0,
)

print(domain_rotation_manager.get_config())
```

`get_config()` returns masked secrets by default and includes:

- `api_configured`
- `monthly_budget`
- `current_spending`
- `active_domain`
- `domains_owned`
- `test_mode`

### CLI

```bash
python domain_rotation_cli.py config
```

The CLI stores config at:

```text
~/.opsechat/domain_config.json
```

## Search for candidate domains

### Python API

```python
from domain_manager import domain_rotation_manager

domains = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=5.0,
    limit=5,
)
print(domains)
```

### CLI

```bash
python domain_rotation_cli.py search
```

## Rotate to a new domain

### Structured result API (recommended)

```python
from domain_manager import domain_rotation_manager

result = domain_rotation_manager.rotate_to_new_domain(max_price=5.0)

if result["success"]:
    print("New domain:", result["domain"])
    print("Cost:", result["cost"])
else:
    print("Rotation failed:", result["error"])
```

### Legacy API (compatibility)

```python
domain = domain_rotation_manager.rotate_domain()
if domain:
    print("Active domain:", domain)
```

### CLI

```bash
python domain_rotation_cli.py rotate
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

## Test mode (safe simulation)

Test mode allows a full rotation flow without calling a registrar purchase API.

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.set_test_mode(True)
result = domain_rotation_manager.rotate_to_new_domain()
print(result)
```

In test mode:

- rotation is marked with `simulated: true`
- purchased domains are tracked in-memory
- `current_spending` is not increased

## Persisting manager state

State export/import is available for tools like the CLI:

```python
state = domain_rotation_manager.get_state()
# save state to JSON externally

domain_rotation_manager.load_state(state)
```

`get_state()` is JSON-serializable (datetimes are ISO-8601 strings).

## Budget behavior

- Purchases are denied when `current_spending + price > monthly_budget`
- `get_budget_status()` returns budget, spending, and remaining funds
- Price strings are normalized automatically (for example `"$2.99"` -> `2.99`)

## Current limitations

- Only Porkbun is implemented out-of-the-box
- DNS record management is not implemented in `DomainRotationManager`
- No registrar failover logic yet

## Security notes

- Do not commit API credentials
- Prefer environment or local config files with restrictive permissions
- Review and rotate API keys periodically
