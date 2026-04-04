# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows via the
Porkbun API. This guide documents the currently implemented interfaces:

- `domain_rotation_cli.py` (primary CLI)
- `rotate-domain.py` (compatibility wrapper for older scripts and docs)
- `domain_manager.py` (programmatic API)

## Current Capabilities

- Search random cheap domains (`.xyz`, `.club`, `.online`, `.site`, `.website`)
- Purchase domains with monthly budget enforcement
- Activate a newly purchased domain
- Persist local CLI state (owned domains, spending, active domain)
- List purchased domains and current budget status
- Get TLD pricing from Porkbun

## Setup

### 1) Get API Credentials

1. Sign up at https://porkbun.com
2. Go to Account -> API Access
3. Create API credentials
4. Keep both values secure:
   - API Key
   - Secret API Key

### 2) Configure the CLI

```bash
python domain_rotation_cli.py config
```

The CLI writes config to:

```text
~/.opsechat/domain_config.json
```

File permissions are restricted to `0600` by the CLI.

## Primary CLI (`domain_rotation_cli.py`)

### Interactive commands

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Non-interactive rotate

```bash
python domain_rotation_cli.py rotate --yes
```

Notes:
- `--yes` only applies to `rotate`.
- Domain selection remains randomized among low-cost TLDs.

## Compatibility CLI (`rotate-domain.py`)

`rotate-domain.py` exists for older references and automation that still call
`python rotate-domain.py ...`.

### Supported commands

```bash
python rotate-domain.py --search
python rotate-domain.py --list-owned
python rotate-domain.py --status
python rotate-domain.py --get-pricing xyz
python rotate-domain.py --buy example.xyz --years 1 --yes
```

Notes:
- `--years` is validated and only valid with `--buy`.
- `--yes` auto-confirms a `--buy` purchase.
- Purchases go through the same budget and persistence logic as the primary CLI.

## Programmatic API

For Python callers, use `DomainRotationManager` from `domain_manager.py`:

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="...", api_secret="...")
manager = DomainRotationManager(api_client=client, monthly_budget=50.0)

candidate = manager.find_cheap_available_domain(max_price=5.0)
if candidate:
    ok = manager.purchase_domain_if_budget_allows(
        candidate["domain"],
        candidate["price"],
        years=1,
    )
    if ok:
        print("Active domain:", manager.get_active_domain())
```

## State Persistence Details

The CLI persists:
- `current_spending`
- `active_domain`
- `owned_domains`

`owned_domains[*].purchased_at` and `expires_at` are stored as ISO-8601 strings
and are converted back to `datetime` values at runtime. This prevents JSON
serialization errors and keeps listing output stable across restarts.

## Troubleshooting

### API credentials missing

If CLI commands fail with missing credentials:

```bash
python domain_rotation_cli.py config
```

### Budget exceeded

Increase monthly budget in config or wait until next budget cycle policy in your
workflow.

### Domain unavailable

Retry search/rotate; random names are generated per attempt.

## Security Notes

- Never commit API keys.
- Keep `~/.opsechat/domain_config.json` protected.
- Use dedicated registrar credentials for automation environments.
