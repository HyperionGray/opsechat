# Domain Rotation Guide

## Overview

OpSecChat can rotate burner-email domains through registrar APIs. The current
production integration is **Porkbun**, implemented in `domain_manager.py` and
exposed through `domain_rotation_cli.py`.

This guide documents the currently implemented interfaces and expected data
flow.

## Implemented Components

- `DomainAPIClient`: registrar abstraction for search, purchase, and pricing.
- `PorkbunAPIClient`: concrete Porkbun API client.
- `DomainRotationManager`: budget enforcement, purchase flow, active domain
  tracking, and persistence import/export.
- `domain_rotation_cli.py`: operator CLI for config, search, rotate, status,
  and list commands.

## Quick Start (CLI)

```bash
# 1) Configure credentials and monthly budget
python domain_rotation_cli.py config

# 2) Show current status
python domain_rotation_cli.py status

# 3) Search low-cost options
python domain_rotation_cli.py search

# 4) Rotate to a new purchased domain (interactive confirmation)
python domain_rotation_cli.py rotate

# 5) List owned domains
python domain_rotation_cli.py list
```

## Programmatic Usage

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=20.0)
manager.configure(api_key="pk_live_xxx", secret_key="sk_live_xxx", monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=3.0, max_attempts=5)
if candidate:
    purchased = manager.purchase_domain_if_budget_allows(candidate["domain"], candidate["price"])
    if purchased:
        print("Active domain:", manager.get_active_domain())
```

## Budget and Rotation Behavior

- Cheap TLD candidates are sampled from:
  - `.xyz`, `.club`, `.online`, `.site`, `.website`
- Purchases are blocked if `current_spending + price > monthly_budget`.
- `rotate_domain()`:
  1. Finds a cheap available domain.
  2. Attempts purchase if budget allows.
  3. Sets the new active domain on success.

## State Persistence

`DomainRotationManager` now provides explicit JSON-safe state helpers:

- `export_state() -> dict`
  - Returns serializable state (`owned_domains`, `active_domain`,
    `monthly_budget`, `current_spending`).
  - Datetimes are exported as ISO strings.

- `import_state(state: dict) -> None`
  - Restores manager state from JSON-safe dictionaries.
  - Rehydrates timestamps and normalizes price values.

The CLI uses these methods to persist state in:

`~/.opsechat/domain_config.json`

## Configuration Introspection

`get_config(mask_secrets=True)` returns current manager configuration for UI/API
usage:

- provider
- configured flag
- masked or unmasked API key/secret
- monthly budget and spending
- active domain
- owned-domain count

This is used by the security/config route layer for status rendering.

## Security Notes

- Never commit API keys.
- Keep registrar credentials scoped and rotated.
- Budget controls limit accidental overspend, but registrar account limits
  should still be configured.

## Extending to Additional Registrars

Implement `DomainAPIClient`:

```python
from domain_manager import DomainAPIClient

class ExampleRegistrarClient(DomainAPIClient):
    def search_domain(self, domain: str) -> dict:
        raise NotImplementedError

    def purchase_domain(self, domain: str, years: int = 1) -> dict:
        raise NotImplementedError

    def get_pricing(self, tld: str) -> dict:
        raise NotImplementedError
```

Then wire it into `DomainRotationManager` via `set_api_client(...)`.
