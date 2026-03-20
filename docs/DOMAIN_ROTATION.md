# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation subsystem for burner email domains. It can:

- Search for inexpensive available domains
- Purchase a domain when budget allows
- Track owned domains and active domain
- Persist local CLI state safely
- Prune expired domain records from saved state
- Use multi-provider fallback through `MultiProviderDomainClient`

## Supported Provider Model

### Built-in provider

- `PorkbunAPIClient` (production-ready integration)

### Multi-provider fallback

`MultiProviderDomainClient` wraps multiple `DomainAPIClient` implementations and:

- checks availability across providers
- remembers the provider that reported availability
- attempts purchase on the preferred provider first
- falls back to remaining providers if purchase fails
- compares pricing across providers

## CLI Quick Start

Use `domain_rotation_cli.py`:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
python domain_rotation_cli.py status
python domain_rotation_cli.py cleanup
```

### `cleanup` command

`cleanup` removes expired domain records from local CLI state and keeps `active_domain` consistent.

## Python API Usage

### Single provider (Porkbun)

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient(api_key="...", api_secret="...")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

domain = manager.rotate_domain()
print("Rotated to:", domain)
print("Budget:", manager.get_budget_status())
```

### Multi-provider fallback

```python
from domain_manager import (
    DomainRotationManager,
    MultiProviderDomainClient,
    PorkbunAPIClient,
)

porkbun_primary = PorkbunAPIClient("key-a", "secret-a")
porkbun_backup = PorkbunAPIClient("key-b", "secret-b")

client = MultiProviderDomainClient(
    providers=[porkbun_primary, porkbun_backup],
    provider_names=["porkbun-primary", "porkbun-backup"],
)

manager = DomainRotationManager(api_client=client, monthly_budget=25.0)
domain = manager.rotate_domain()
print(domain)
```

## CLI State File

`domain_rotation_cli.py` stores state at:

`~/.opsechat/domain_config.json`

`owned_domains` records serialize `purchased_at` and `expires_at` as ISO-8601 timestamps and are parsed back into `datetime` objects on load.

## Security Notes

- Keep API keys out of git
- Store secrets with restrictive file permissions (CLI uses `0600`)
- Set a strict monthly budget
- Prefer short registration terms for rotating burner domains
