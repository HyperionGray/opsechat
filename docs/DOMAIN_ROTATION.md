# Domain Rotation

This document describes the current domain rotation implementation used by the burner email subsystem.

## What is implemented

- Registrar integration through `domain_manager.py`
- Runtime config for registrar credentials and monthly budget
- Budget-aware domain purchase checks
- Active-domain rotation flow
- CLI configuration/state persistence in `domain_rotation_cli.py`
- Email settings page integration at:
  - `/<path>/email/config`
  - `/<path>/email/domain/rotate`

## Supported registrar

### Porkbun

Porkbun is the currently supported registrar backend through `PorkbunAPIClient`.

Endpoints used:

- `domain/check`
- `domain/create`
- `pricing/get`
- `domain/listAll`

## Runtime API (`DomainRotationManager`)

Main methods:

- `configure(api_key, api_secret, monthly_budget=50.0, provider="porkbun")`
- `get_config()`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_domain()`
- `get_active_domain()`
- `get_budget_status()`
- `export_state()`
- `load_state(state)`

Notes:

- Credentials are in-memory only unless explicitly saved by a wrapper (like the CLI config file).
- `export_state()` and `load_state()` handle datetime serialization/deserialization so saved state is JSON-safe.

## CLI usage

`domain_rotation_cli.py` is the operator interface for managing domain rotation:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

The CLI stores config in:

- `~/.opsechat/domain_config.json`

Stored runtime state is under the `state` key and can still load legacy flat fields for backward compatibility.

## Web integration

The email config route in `email_routes.py` now handles:

- SMTP form (`action=configure_smtp`)
- IMAP form (`action=configure_imap`)
- Domain API form (`action=configure_domain_api`)

The rotate endpoint:

- Returns JSON for AJAX/API clients
- Redirects back to `/email/config` for browser form posts with a user-facing status message

## Operational guidance

- Start with a low monthly budget (for example, 10-20 USD)
- Keep per-domain max price low (default logic searches around cheap TLD pricing)
- Monitor `current_spending` and `remaining` via `get_budget_status()`
- Use one-year registrations for short-lived burner domain strategy
