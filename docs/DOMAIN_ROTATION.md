# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation subsystem for burner email workflows. It can:

- configure a registrar client (currently Porkbun),
- discover low-cost available domains,
- enforce a monthly spending budget,
- purchase and activate a new domain,
- expose state for both CLI and web UI flows.

All state remains in-memory unless you explicitly persist it through the CLI config file.

## Current Implementation Scope

Implemented now:

- `DomainRotationManager` in `domain_manager.py`
- `domain_rotation_cli.py` commands:
  - `config`, `status`, `search`, `rotate`, `list`
- Web routes in `email_routes.py`:
  - `/<path>/email/config`
  - `/<path>/email/domain/rotate`

Not implemented in this module:

- DNS record management
- multi-registrar orchestration
- automated cron scheduler built into the app

## Quick Start (CLI)

```bash
# 1) Configure API credentials and budget
python domain_rotation_cli.py config

# 2) Check current status
python domain_rotation_cli.py status

# 3) Search for cheap available domains
python domain_rotation_cli.py search

# 4) Purchase and rotate to a new domain
python domain_rotation_cli.py rotate

# 5) List owned/known purchased domains
python domain_rotation_cli.py list
```

The CLI persists state at:

- `~/.opsechat/domain_config.json` (permissions set to `0600`)

## Quick Start (Web)

1. Open `/<secret-path>/email/config`.
2. In **Domain API (Porkbun)**:
   - set API key,
   - set API secret,
   - set monthly budget.
3. Submit **Configure Domain API**.
4. Use **Rotate to New Domain**.

When rotation succeeds, the active burner domain is updated and shown in the configuration page.

## Python API Reference (Current)

From `domain_manager.py`:

- `configure(api_key, secret_key, monthly_budget=None, provider="porkbun")`
  - Creates and assigns a `PorkbunAPIClient`.
- `get_config()`
  - Returns non-sensitive configuration and budget summary.
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
  - Returns one candidate domain or `None`.
- `search_cheap_domains(max_price=5.0, limit=5, max_attempts_per_result=5)`
  - Returns a list of candidate domains.
- `purchase_domain_if_budget_allows(domain, price)`
  - Purchases only if monthly budget allows.
- `rotate_domain()`
  - Returns active domain string on success, otherwise `None`.
- `rotate_domain_with_result()`
  - Structured response for route/API use:
    - `{"success": True, "domain": "...", "budget_status": {...}}`
    - or failure object with `error`.
- `export_state()` / `import_state(state)`
  - JSON-safe persistence helpers. Datetime values are serialized to ISO-8601 and restored on import.

## Budget Behavior

- `monthly_budget` is enforced before purchase.
- `current_spending` increments on successful purchases.
- `get_budget_status()` returns:
  - `monthly_budget`
  - `current_spending`
  - `remaining`
  - `domains_owned`

If budget would be exceeded, purchase is denied.

## Data and Serialization Notes

Domain records include:

- `domain`
- `price`
- `purchased_at`
- `expires_at`

For persistence:

- in-memory: `datetime` objects
- serialized: ISO-8601 strings

This avoids JSON serialization failures in CLI state saves.

## Troubleshooting

### Rotation returns failure

Common causes:

- API credentials missing/invalid
- no available domain under price threshold
- monthly budget exhausted

Check:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
```

### Web config succeeds but rotate fails

Ensure the app has a valid registrar config in memory and available budget.

### Purchased domains not showing in CLI

State is local to the config file used by the CLI (`~/.opsechat/domain_config.json`).  
If this file is deleted or moved, previous CLI state will not appear.

## Security Notes

- Do not commit registrar API keys.
- Use dedicated API credentials with minimal scope when possible.
- Keep monthly budgets conservative to reduce accidental spend.
- Treat domain purchases as billable, irreversible operations.
