# Domain Rotation Guide

## Overview

OpSecChat includes a lightweight domain rotation system used by burner-email workflows.
It can:

- check random low-cost domains through Porkbun,
- purchase within a monthly budget,
- track owned domains and active domain,
- persist local state safely for CLI usage.

## Current Capabilities

Implemented in `domain_manager.py`:

- `DomainRotationManager.find_cheap_available_domain(...)`
- `DomainRotationManager.purchase_domain_if_budget_allows(...)`
- `DomainRotationManager.rotate_domain()`
- `DomainRotationManager.rotate_domain_with_details()`
- `DomainRotationManager.prune_expired_domains()`
- `DomainRotationManager.export_state()` / `load_state()`
- `DomainRotationManager.configure(...)` / `get_config()`

CLI is in `domain_rotation_cli.py`.

## Supported Registrar

- **Porkbun** via `PorkbunAPIClient`

You can add another registrar by subclassing `DomainAPIClient`.

## Setup

### 1. Get Porkbun API Credentials

1. Sign up at [porkbun.com](https://porkbun.com)
2. Open Account -> API Access
3. Generate API credentials
4. Save:
   - API key
   - Secret API key

### 2. Configure CLI

```bash
python domain_rotation_cli.py config
```

This writes `~/.opsechat/domain_config.json` with mode `0600`.

## CLI Usage

```bash
# Show current budget/domain status
python domain_rotation_cli.py status

# Search for cheap domains (read-only)
python domain_rotation_cli.py search

# Purchase and rotate to a new domain (prompts for confirmation)
python domain_rotation_cli.py rotate

# List owned domains from local state
python domain_rotation_cli.py list

# Remove expired domains from local state
python domain_rotation_cli.py prune
```

## Web/API Usage

Within the app, the endpoint below rotates domain and returns structured JSON:

- `POST /<path>/email/domain/rotate`

Response format:

```json
{
  "success": true,
  "domain": "abc123xy.xyz",
  "price": 1.99
}
```

Failure example:

```json
{
  "success": false,
  "domain": null,
  "error": "Could not find available cheap domain"
}
```

## State Persistence

Recent improvement: state serialization is now robust.

- Datetime fields are saved as ISO strings.
- Datetime fields are parsed back on load.
- Non-numeric prices are ignored instead of crashing.
- Expired domains can be pruned and active domain is updated accordingly.

## Budget Behavior

- Purchase is denied when `current_spending + price > monthly_budget`.
- Budget status is available via:
  - `DomainRotationManager.get_budget_status()`
  - CLI `status`
  - email config route data

## Security Notes

- Do not commit API keys.
- Use registrar sub-keys where possible.
- Keep budget conservative to limit accidental spending.

## Troubleshooting

### API credentials missing

Run:

```bash
python domain_rotation_cli.py config
```

### Domain purchase fails

Check:

- registrar account balance,
- key permissions,
- monthly budget remaining.

### Local list contains stale domains

Run:

```bash
python domain_rotation_cli.py prune
```
