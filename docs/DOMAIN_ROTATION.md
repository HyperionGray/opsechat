# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems through
`domain_manager.py` and `domain_rotation_cli.py`. This lets operators rotate
domains with explicit budget controls.

## Current Implementation Status

Implemented now:
- Porkbun registrar client (`PorkbunAPIClient`)
- Runtime manager configuration (`DomainRotationManager.configure`)
- Provider registry (`add_api_client`, `set_active_provider`)
- Cheap domain search (`search_cheap_domains`, `find_cheap_available_domain`)
- Purchase with budget checks (`purchase_domain_if_budget_allows`)
- Rich rotation payload (`rotate_to_new_domain`)
- Test-mode simulation (`set_test_mode`)
- CLI config/state persistence (`domain_rotation_cli.py`)

Not implemented in code (remove stale assumptions):
- DNS record management methods (`configure_domain_dns`)
- `python -m domain_manager ...` subcommands (use `domain_rotation_cli.py` instead)

## Setup

### 1) Get Porkbun API credentials

1. Sign up at [porkbun.com](https://porkbun.com)
2. Open Account -> API Access
3. Enable API access and save:
   - API Key
   - Secret Key

### 2) Configure via CLI

```bash
python domain_rotation_cli.py config
```

The CLI stores config in:

```text
~/.opsechat/domain_config.json
```

with file mode `0600`.

## Runtime Usage (Python API)

```python
from domain_manager import domain_rotation_manager

# Configure provider and budget
domain_rotation_manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
    monthly_budget=20.0,
)

# Search candidates
candidates = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=3.0,
    limit=5,
)
print(candidates)

# Rotate and purchase one
result = domain_rotation_manager.rotate_to_new_domain()
print(result)
# {"success": True, "domain": "...", "cost": 2.99, "provider": "porkbun"}
```

## CLI Usage

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Test Mode

Use test mode to verify flows without registrar purchase calls:

```python
from domain_manager import DomainRotationManager
from domain_manager import DomainAPIClient

mock_client = DomainAPIClient("k", "s")  # replace with real subclass in practice
mgr = DomainRotationManager(mock_client, monthly_budget=10.0)
mgr.set_test_mode(True)
mgr.purchase_domain_if_budget_allows("example.xyz", 1.50)
```

In test mode, purchase state updates locally but external API purchase is skipped.

## Budget Behavior

- `monthly_budget`: configured cap
- `current_spending`: sum of successful purchases
- purchase is blocked when `current_spending + price > monthly_budget`
- status is available via `get_budget_status()`

## Troubleshooting

### "No API client configured"
Call `configure(...)` before search/rotate or run CLI `config`.

### Budget exceeded
Increase monthly budget or reduce target max price.

### No available cheap domains
Increase attempts, expand TLD list, or raise max price.

## Extending to Additional Registrars

```python
from domain_manager import DomainAPIClient, domain_rotation_manager

class NamecheapAPIClient(DomainAPIClient):
    def search_domain(self, domain: str):
        raise NotImplementedError
    def purchase_domain(self, domain: str, years: int = 1):
        raise NotImplementedError
    def get_pricing(self, tld: str):
        raise NotImplementedError

domain_rotation_manager.add_api_client("namecheap", NamecheapAPIClient("k", "s"))
domain_rotation_manager.set_active_provider("namecheap")
```

## Summary

Domain rotation is operational for Porkbun with budget enforcement, state
tracking, and CLI support. Multi-provider plumbing now exists in the manager,
and additional registrar adapters can be added incrementally.
