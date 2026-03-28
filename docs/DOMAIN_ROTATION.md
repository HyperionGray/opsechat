# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows. The
rotation manager can discover cheap domains, purchase within a monthly budget,
and track active/owned domains in memory.

## Supported Providers

- `porkbun` (API key + secret key)
- `namecheap` (API key + username + allowed client IP)

Both providers are implemented in `domain_manager.py` and can be selected in
`domain_rotation_cli.py`.

## CLI Quick Start

### 1) Configure provider credentials

```bash
python domain_rotation_cli.py config
```

During configuration, choose a provider:
- `porkbun`
- `namecheap`

Then provide provider-specific credentials and a monthly budget.

### 2) View current status

```bash
python domain_rotation_cli.py status
```

This shows:
- active domain
- active provider
- monthly budget/spending/remaining
- number of purchased domains

### 3) Search for cheap domains

```bash
python domain_rotation_cli.py search
```

### 4) Purchase and rotate

```bash
python domain_rotation_cli.py rotate
```

### 5) List purchased domains

```bash
python domain_rotation_cli.py list
```

The list includes provider, price, purchase date, and expiry date.

## Python API Usage

### Configure a manager

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=25.0)

manager.configure(
    provider="porkbun",
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=25.0,
)
```

Namecheap configuration:

```python
manager.configure(
    provider="namecheap",
    api_key="namecheap_api_key",
    username="your_namecheap_username",
    client_ip="203.0.113.10",
    monthly_budget=25.0,
)
```

### Search candidates

```python
domains = manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=5.00,
    limit=5,
)
```

### Rotate to a newly purchased domain

```python
result = manager.rotate_to_new_domain(max_price=5.0)
if result["success"]:
    print("new domain:", result["domain"])
    print("provider:", result.get("provider"))
else:
    print("rotation failed:", result["error"])
```

### Query budget status

```python
print(manager.get_budget_status())
```

## Budget Behavior

- Purchases are blocked if `current_spending + price > monthly_budget`.
- Spending is tracked in memory and by CLI config state file.
- Domain entries track provider, purchase timestamp, and expiry timestamp.

## Security Notes

- Do not commit registrar credentials.
- Prefer environment-specific secret storage for automation.
- Namecheap requires the caller IP to be allowlisted in Namecheap API settings.

## Troubleshooting

### "No API client configured"
- Run `python domain_rotation_cli.py config`.
- Confirm provider-specific fields are present.

### "Budget exceeded"
- Increase monthly budget in CLI config, or wait until budget is reset.

### Namecheap request failures
- Verify API key and username.
- Verify `client_ip` is allowlisted in Namecheap API settings.

## Related Files

- `domain_manager.py`
- `domain_rotation_cli.py`
- `tests/test_domain_manager.py`
- `docs/setup/DOMAIN_API_SETUP.md`
- `docs/setup/DOMAIN_REGISTRAR_API.md`
