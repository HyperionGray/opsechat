# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation component for burner email workflows:

- `domain_manager.py` provides:
  - `PorkbunAPIClient` for registrar API calls
  - `DomainRotationManager` for budget-aware rotation logic
- `domain_rotation_cli.py` provides operator commands for configuration and rotation

The implementation is intentionally conservative:

- In-memory runtime behavior by default
- Explicit budget checks before any purchase
- JSON-safe state export/import for CLI persistence
- Masked secrets in configuration readouts

## Supported Provider

Currently implemented provider:

- Porkbun API (`PorkbunAPIClient`)

The base class `DomainAPIClient` is abstract and intended for extension with additional registrars.

## Core Manager API (Current)

`DomainRotationManager` currently supports:

- `configure(api_key, secret_key|api_secret, monthly_budget=None)`
  - Sets the active API client and optional budget
  - Validates required credentials
- `get_config()`
  - Returns sanitized configuration details
  - Masks API key/secret values
- `export_state()`
  - Serializes owned domains and timestamps into JSON-safe values
- `import_state(state)`
  - Restores state and normalizes timestamp/price data
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
  - Probes random domains in low-cost TLDs
- `purchase_domain_if_budget_allows(domain, price)`
  - Enforces monthly budget before purchasing
- `rotate_domain()`
  - Rotates to a new active domain, returns domain string or `None`
- `rotate_domain_with_result()`
  - API-oriented wrapper with structured success/error payload

## Web Route Integration

The email security routes use the manager directly:

- `/email/config` reads manager config via `get_config()`
- `/email/domain/rotate` triggers `rotate_domain_with_result()`

The rotate endpoint returns JSON in a stable shape:

- Success:
  - `{"success": true, "domain": "...", "price": <float|null>, "active_domain": "..."}`
- Failure:
  - `{"success": false, "error": "...", "active_domain": <string|null>}`

## CLI Usage

Use `domain_rotation_cli.py`:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Persistence Model

The CLI stores config under:

- `~/.opsechat/domain_config.json`

Manager state persistence now uses:

- `manager.export_state()` when saving
- `manager.import_state(config)` when loading

This avoids timestamp-shape drift and keeps older saved values readable.

## Budget and Safety Notes

- Configure a monthly budget before enabling purchases.
- Purchases are real registrar actions and can incur cost.
- Do not commit API credentials; keep them in local config or environment-only workflows.

## Extension Notes

To add a new registrar:

1. Implement a `DomainAPIClient` subclass.
2. Add configuration and client construction flow (CLI or web route layer).
3. Reuse `DomainRotationManager` for budget/state management.

