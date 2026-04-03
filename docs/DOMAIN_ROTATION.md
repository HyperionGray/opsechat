# Domain Rotation Guide

## Overview

OpSecChat includes a practical CLI workflow for purchasing and rotating low-cost
domains (currently via Porkbun) for burner email scenarios.

The supported implementation in this repository is:

- `domain_manager.py`:
  - `PorkbunAPIClient`
  - `DomainRotationManager`
- `domain_rotation_cli.py`:
  - `config`
  - `status`
  - `search`
  - `rotate`
  - `list`

This guide documents only those implemented interfaces.

## Quick Start

1. Get Porkbun API credentials from <https://porkbun.com/account/api>.
2. Configure CLI credentials:

```bash
python domain_rotation_cli.py config
```

3. Check status:

```bash
python domain_rotation_cli.py status
```

4. Search for inexpensive available domains:

```bash
python domain_rotation_cli.py search
```

5. Rotate (purchase + activate) a new domain:

```bash
python domain_rotation_cli.py rotate
```

6. List owned domains:

```bash
python domain_rotation_cli.py list
```

## Configuration and State

The CLI stores config and runtime state in:

`~/.opsechat/domain_config.json`

Stored values include:

- `api_key`
- `api_secret`
- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains` (including purchase/expiry timestamps)

The file is written with mode `0600`.

### Persistence behavior

Domain purchase records include datetime values (`purchased_at`, `expires_at`).
These values are serialized to ISO-8601 in JSON and converted back to datetime
objects on load so that `list` and `status` remain stable across process restarts.

## Cost and Safety Controls

- Configurable monthly budget (`monthly_budget`)
- Current spending tracking (`current_spending`)
- Purchase is denied if `current_spending + price > monthly_budget`
- Search defaults to cheap TLDs:
  - `.xyz`
  - `.club`
  - `.online`
  - `.site`
  - `.website`

## CLI Command Reference

```bash
python domain_rotation_cli.py config   # Configure API key/secret and budget
python domain_rotation_cli.py status   # Show budget + active domain
python domain_rotation_cli.py search   # Probe for available low-cost domains
python domain_rotation_cli.py rotate   # Purchase and activate a domain
python domain_rotation_cli.py list     # List owned domains and expiry metadata
```

## Troubleshooting

### "API credentials not configured"

Run:

```bash
python domain_rotation_cli.py config
```

### "Could not find an available cheap domain within budget"

- Retry `search` and `rotate` later (availability and promotions vary)
- Increase monthly budget if your remaining budget is too low

### Date/time output shows "Unknown"

This means the saved record contains invalid or missing datetime values.
The CLI will continue running and skip strict formatting failures.

## Extending to Other Registrars

To add a new registrar, subclass `DomainAPIClient` in `domain_manager.py`
and implement:

- `search_domain(domain: str) -> Dict`
- `purchase_domain(domain: str, years: int = 1) -> Dict`
- `get_pricing(tld: str) -> Dict`
