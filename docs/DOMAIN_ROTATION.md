# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation CLI for managing burner email domains via
registrar APIs. The current registrar implementation is Porkbun.

Primary tools:

- `python domain_rotation_cli.py ...`
- `python rotate-domain.py ...` (compatibility wrapper)

Both commands support the same arguments.

## Configure Credentials

```bash
python domain_rotation_cli.py config
```

Configuration is stored at:

`~/.opsechat/domain_config.json` (permissions `0600`)

Stored fields include:

- `api_key`
- `api_secret`
- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains` (with ISO-8601 timestamps)

## Available Commands

```bash
# Show status
python domain_rotation_cli.py status

# Search for affordable domains
python domain_rotation_cli.py search --max-price 3.00 --attempts 8

# Purchase and rotate domain (interactive confirmation)
python domain_rotation_cli.py rotate --max-price 3.00

# Purchase and rotate domain (non-interactive automation)
python domain_rotation_cli.py rotate --yes --max-price 3.00

# List all domains tracked in local state
python domain_rotation_cli.py list
```

## Notes on Persistence

- Domain entries are persisted with ISO timestamps and restored as datetimes at
  runtime.
- This avoids JSON serialization failures after successful purchases.
- If timestamp parsing fails for a legacy entry, the CLI still loads the entry
  and prints `unknown` for that date field.

## Registrar Support

Current support:

- Porkbun API (`PorkbunAPIClient`)

Extension point:

- Subclass `DomainAPIClient` and implement:
  - `search_domain(domain: str) -> Dict`
  - `purchase_domain(domain: str, years: int = 1) -> Dict`
  - `get_pricing(tld: str) -> Dict`

## Security Practices

- Never commit API credentials.
- Keep `domain_config.json` local and protected (`0600`).
- Use a strict monthly budget to prevent accidental overspend.
- Rotate registrar API keys periodically.
