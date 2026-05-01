# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows.
The implementation is centered on `DomainRotationManager` in `src/python/domain_manager.py`.

Current capabilities:

- Registrar client abstraction via `DomainAPIClient`
- Porkbun implementation via `PorkbunAPIClient`
- Cheap-domain discovery (`search_cheap_domains`)
- Budget-aware purchase and rotation (`purchase_domain_if_budget_allows`, `rotate_to_new_domain`)
- Optional multi-provider registration (`add_api_client`, `use_api_client`)

## Registrar Setup (Porkbun)

1. Create/sign in to [porkbun.com](https://porkbun.com)
2. Open account API settings
3. Generate and store:
   - API key
   - Secret API key

## Configure in OpSecChat

### Web UI

1. Open `/<path>/email/config`
2. Submit `Domain API` settings:
   - API key
   - API secret
   - Monthly budget

### Python API

```python
from domain_manager import domain_rotation_manager

ok = domain_rotation_manager.configure(
    api_key="pk1_example",
    secret_key="sk1_example",
    monthly_budget=25.0,
)

print("configured:", ok)
print(domain_rotation_manager.get_config())
```

## Python API Usage

### Search available low-cost domains

```python
from domain_manager import domain_rotation_manager

matches = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=3.00,
    limit=5,
)
for item in matches:
    print(item["domain"], item["price"])
```

### Rotate to a new domain

```python
from domain_manager import domain_rotation_manager

result = domain_rotation_manager.rotate_to_new_domain(max_price=5.00, max_attempts=10)
if result.get("success"):
    print("active domain:", result["active_domain"])
else:
    print("rotation failed:", result.get("message"))
```

### Budget management

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.set_monthly_budget(40.0)
status = domain_rotation_manager.get_budget_status()
print(status)
```

## CLI Usage

Use the built-in CLI wrapper:

```bash
python bin/domain-rotation.py config
python bin/domain-rotation.py status
python bin/domain-rotation.py search
python bin/domain-rotation.py rotate
python bin/domain-rotation.py list
```

Notes:

- `rotate` is interactive and asks for purchase confirmation.
- CLI state is persisted in `~/.opsechat/domain_config.json`.
- Owned domain timestamps are stored in ISO format and restored automatically.

## Automation

For unattended automation (cron), prefer a Python one-liner over the interactive CLI:

```bash
0 2 * * 0 cd /path/to/opsechat && python3 -c "from domain_manager import domain_rotation_manager; domain_rotation_manager.configure('pk1_x','sk1_y',20.0); print(domain_rotation_manager.rotate_to_new_domain())"
```

Replace credentials with secure secret loading in production environments.

## Multi-Provider Extension

The manager supports multiple named provider clients:

```python
from domain_manager import DomainAPIClient, domain_rotation_manager

class ExampleRegistrar(DomainAPIClient):
    def search_domain(self, domain: str):
        raise NotImplementedError
    def purchase_domain(self, domain: str, years: int = 1):
        raise NotImplementedError
    def get_pricing(self, tld: str):
        raise NotImplementedError

client = ExampleRegistrar("api-key", "api-secret")
domain_rotation_manager.add_api_client("example", client)
domain_rotation_manager.use_api_client("example")
```

## Troubleshooting

### "No API client configured"

Call `configure(...)` first or submit API credentials in `/email/config`.

### Rotation fails with budget message

Inspect:

```python
from domain_manager import domain_rotation_manager
print(domain_rotation_manager.get_budget_status())
```

Increase the budget or lower `max_price`.

### No cheap domains found

Increase attempts and widen TLD set:

```python
matches = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club", "online", "site", "website"],
    max_price=6.0,
    limit=10,
    max_attempts=40,
)
```
