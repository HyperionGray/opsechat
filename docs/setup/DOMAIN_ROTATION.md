# Domain Rotation Guide

## Overview

OpSecChat supports domain rotation for burner email use-cases through `domain_manager.py` and `domain_rotation_cli.py`.

Current production support:
- **Porkbun API** (implemented)
- Additional registrars can be added by subclassing `DomainAPIClient`

## What is implemented

The current `DomainRotationManager` supports:

- API credential configuration with budget limits
- single-domain rotation (`rotate_domain`)
- multi-candidate search (`search_available_domains`)
- budget tracking (`get_budget_status`)
- JSON-safe state persistence (`export_state` / `load_state`)

Not implemented in this repository:
- DNS record management helpers
- multi-registrar registry/dispatcher
- pattern-based domain generation APIs beyond random generation

## Setup

### 1. Get Porkbun API credentials

1. Sign up at [porkbun.com](https://porkbun.com)
2. Open Account -> API Access
3. Enable API and copy:
   - API key
   - Secret API key

### 2. Configure via web UI

1. Open `/<secret-path>/email/config`
2. Fill in:
   - Porkbun API key
   - Porkbun API secret
   - monthly budget
3. Save

### 3. Configure via CLI

```bash
python domain_rotation_cli.py config
```

The CLI stores config and serialized manager state at:
`~/.opsechat/domain_config.json` (mode `0600`).

## CLI reference

```bash
python domain_rotation_cli.py config   # set API keys + budget
python domain_rotation_cli.py status   # show active domain and budget
python domain_rotation_cli.py search   # list up to 5 cheap available domains
python domain_rotation_cli.py rotate   # purchase + activate one domain
python domain_rotation_cli.py list     # list owned domains
```

## Python API reference

### Basic rotation

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("pk1_xxx", "sk1_yyy")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

result = manager.rotate_domain()
if result["success"]:
    print("active:", result["active_domain"])
else:
    print("error:", result["message"])
```

### Multi-candidate search (new)

`search_available_domains` finds several cheap available candidates and sorts by price.

```python
candidates = manager.search_available_domains(
    max_price=5.0,
    max_attempts=30,
    max_results=5,
    tlds=["xyz", "club", "online"],
)

for candidate in candidates:
    print(candidate["domain"], candidate["price"], candidate["currency"])
```

### State persistence (new)

Use these helpers when writing manager state into JSON files:

```python
state = manager.export_state()   # datetimes become ISO strings

restored = DomainRotationManager(api_client=client)
restored.load_state(state)       # ISO strings become datetime objects
```

This is what the CLI uses to avoid serialization errors for `owned_domains`.

## Budget behavior

- Purchases are denied when `current_spending + price > monthly_budget`
- `get_budget_status()` returns:
  - `monthly_budget`
  - `current_spending`
  - `remaining`
  - `domains_owned`

## Security notes

- Never commit API keys.
- Prefer dedicated registrar API credentials for this app.
- Keep monthly budget conservative and rotate only as needed.

## Troubleshooting

### "No API client configured"

Configure credentials first:

```bash
python domain_rotation_cli.py config
```

or via the web config route.

### "Could not find available cheap domain"

- Increase `max_attempts`
- Increase `max_price`
- expand TLD list in `search_available_domains(..., tlds=[...])`

### Budget exceeded

Increase monthly budget in UI/CLI or wait for your own reset workflow.
