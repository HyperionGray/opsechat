# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows.
The implementation is centered on `DomainRotationManager` in `domain_manager.py`.

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
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py rotate --yes
python domain_rotation_cli.py rotate-auto --dry-run --json
python domain_rotation_cli.py rotate-auto --max-price 3.00 --max-attempts 40 --json
python domain_rotation_cli.py list
```

Notes:

- `rotate` is interactive and asks for purchase confirmation.
- `rotate --yes` skips the confirmation prompt for scripted runs.
- `rotate-auto` is non-interactive and returns exit codes for automation tools.
- CLI state is persisted in `~/.opsechat/domain_config.json`.
- Owned domain timestamps are stored in ISO format and restored automatically.

### CLI exit codes (`rotate-auto`)

- `0`: Success (or dry-run candidate found)
- `2`: Budget exhausted
- `3`: No candidate domain found in attempt window
- `4`: Purchase call failed

## Automation

For unattended automation, use `rotate-auto` with environment variables.

Environment variables supported by the CLI:

- `OPSECHAT_DOMAIN_API_KEY`
- `OPSECHAT_DOMAIN_API_SECRET`
- `OPSECHAT_DOMAIN_MONTHLY_BUDGET`

These override values from `~/.opsechat/domain_config.json` at runtime.

Example cron entry:

```bash
0 2 * * 0 cd /path/to/opsechat && OPSECHAT_DOMAIN_API_KEY=pk1_x OPSECHAT_DOMAIN_API_SECRET=sk1_y OPSECHAT_DOMAIN_MONTHLY_BUDGET=20 python3 domain_rotation_cli.py rotate-auto --max-price 4.00 --json >> /var/log/opsechat-domain-rotation.log 2>&1
```

In production, inject these via your scheduler or service environment rather than hardcoding secrets.

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
