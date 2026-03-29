# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email usage with budget
controls and registrar abstraction.

The domain subsystem now supports:

- Porkbun
- Namecheap

Both are integrated through `DomainAPIClient` implementations in
`domain_manager.py`.

## Current Runtime API

The active manager API is centered around `DomainRotationManager`:

- `configure(...)`
- `find_cheap_available_domain(...)`
- `search_cheap_domains(...)`
- `purchase_domain_if_budget_allows(...)`
- `rotate_domain()` (returns domain string or `None`)
- `rotate_domain_with_details()` / `rotate_to_new_domain()` (structured result)
- `get_budget_status()`
- `export_state()` / `import_state()`

## Configure a Registrar

### Porkbun

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
manager.configure(
    registrar="porkbun",
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
    monthly_budget=50.0,
)
```

### Namecheap

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
manager.configure(
    registrar="namecheap",
    api_key="namecheap_api_key",
    api_user="namecheap_api_username",
    username="namecheap_account_username",  # optional, defaults to api_user
    client_ip="203.0.113.10",               # required by Namecheap API
    use_sandbox=False,
    monthly_budget=50.0,
)
```

## Rotate Domains Programmatically

```python
from domain_manager import domain_rotation_manager

result = domain_rotation_manager.rotate_to_new_domain()
if result["success"]:
    print("New domain:", result["domain"])
    print("Price:", result["price"])
else:
    print("Rotation failed:", result["error"])
```

## CLI Usage

Use the built-in CLI:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
python domain_rotation_cli.py status
```

`config` now supports selecting `porkbun` or `namecheap` and stores manager
state (budget, spending, owned domains, active domain) in:

`~/.opsechat/domain_config.json`

## Budget Controls

Every purchase goes through `purchase_domain_if_budget_allows` and is blocked if:

`current_spending + price > monthly_budget`

Budget status:

```python
status = domain_rotation_manager.get_budget_status()
print(status["monthly_budget"], status["current_spending"], status["remaining"])
```

## Cheap TLD Strategy

`find_cheap_available_domain()` samples from:

- `.xyz`
- `.club`
- `.online`
- `.site`
- `.website`

If a registrar availability API does not return a price, OpSecChat falls back to
registrar pricing endpoints where available.

## Security Notes

- Keep API credentials out of version control.
- Prefer environment variables or local secure config files for automation.
- Restrict Namecheap API client IP in your Namecheap control panel.
- Set conservative monthly budgets first, then increase as needed.

## Troubleshooting

### "No API client configured"

Run `python domain_rotation_cli.py config` and set registrar credentials.

### Rotation fails on Namecheap purchase

Namecheap can require additional profile/contact data for domain purchases.
The raw API error is returned in `message` for troubleshooting.

### Budget exceeded

Increase budget in config or wait for your operational reset policy before
retrying purchases.
