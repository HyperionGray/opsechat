# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation subsystem for burner email workflows.
It can:

- search for low-cost available domains
- purchase within a monthly budget limit
- track active and owned domains in memory
- persist/restore manager state through the CLI config file
- run in dry-run mode for safe testing

## Current Registrar Support

- Porkbun (implemented)
- extensible provider model through `DomainAPIClient`

The `DomainRotationManager` now supports named providers so additional
registrars can be plugged in without changing the rotation flow.

## CLI Usage

Use `domain_rotation_cli.py`:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

Config is stored at:

```text
~/.opsechat/domain_config.json
```

The CLI persists manager state (`current_spending`, `active_domain`,
`owned_domains`) using the manager's JSON-safe export/load helpers.

## Python API

### Basic configuration and rotation

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=10.0)
manager.configure(
    api_key="pk_live_...",
    secret_key="sk_live_...",
    monthly_budget=10.0,
    provider_name="porkbun",
)

result = manager.rotate_to_new_domain(max_price=3.0)
if result["success"]:
    print("New domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

### Searching cheap domains

```python
candidates = manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=2.5,
    limit=5,
    max_attempts=25,
)
print(candidates)
```

### Dry-run mode (no real purchase)

```python
manager.set_test_mode(True)
result = manager.rotate_to_new_domain(max_price=2.0)
print(result)
```

### State export/load

```python
state = manager.export_state()

new_manager = DomainRotationManager()
new_manager.load_state(state)
```

## Multi-Provider Extension Pattern

```python
from domain_manager import DomainAPIClient, DomainRotationManager

class ExampleRegistrarClient(DomainAPIClient):
    def search_domain(self, domain: str):
        raise NotImplementedError

    def purchase_domain(self, domain: str, years: int = 1):
        raise NotImplementedError

    def get_pricing(self, tld: str):
        raise NotImplementedError

manager = DomainRotationManager(monthly_budget=20.0)
manager.add_api_client("example", ExampleRegistrarClient("key", "secret"))
manager.set_active_provider("example")
```

## Budget and Safety Notes

- purchases are denied when `current_spending + price > monthly_budget`
- purchase state is tracked per manager instance
- API keys should never be committed to git
- keep CLI config file permissions restricted (the CLI sets mode `0600`)

## Troubleshooting

### "No API client configured"

Run `python domain_rotation_cli.py config` first, or call `manager.configure(...)`
before search/rotate calls.

### "No available domain found"

Increase `max_attempts`, broaden TLD list, or raise `max_price`.

### "Purchase failed or budget exceeded"

Check `manager.get_budget_status()` and verify provider credentials.
