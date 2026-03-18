# Domain Rotation Guide

## Overview

OpSecChat includes domain rotation utilities for burner email workflows.
Current implementation supports:

- Porkbun registrar API integration
- Budget-aware purchases
- Local state persistence for owned domains and spending
- Cleanup of expired local domain records

The implementation lives in:

- `domain_manager.py` (API clients and rotation logic)
- `domain_rotation_cli.py` (operator-facing CLI)

## Quick Start

Configure API credentials:

```bash
python domain_rotation_cli.py config
```

Check status:

```bash
python domain_rotation_cli.py status
```

Search candidate domains:

```bash
python domain_rotation_cli.py search
```

Rotate to a newly purchased domain:

```bash
python domain_rotation_cli.py rotate
```

Rotate non-interactively (automation-friendly):

```bash
python domain_rotation_cli.py rotate --yes
```

List locally tracked domains:

```bash
python domain_rotation_cli.py list
```

Prune expired local records:

```bash
python domain_rotation_cli.py cleanup
```

## Persisted State

The CLI stores configuration and rotation state in:

`~/.opsechat/domain_config.json`

Persisted fields include:

- `api_key`
- `api_secret`
- `monthly_budget`
- `current_spending`
- `owned_domains`
- `active_domain`

Datetime values inside `owned_domains` are serialized as ISO-8601 strings
and automatically parsed when state is loaded.

## Budget Behavior

Budget checks happen before purchase:

- Purchases are rejected when `current_spending + price > monthly_budget`
- `status` shows current spend and remaining budget
- `rotate` also checks budget before searching/purchasing

## Operational Notes

- The cleanup command only affects local tracked state.
- Domain ownership with the registrar is unchanged by local cleanup.
- For accurate billing and purchased-domain records, always confirm in your
  registrar dashboard.

## Troubleshooting

### "API credentials not configured"

Run:

```bash
python domain_rotation_cli.py config
```

### Purchase fails unexpectedly

Check:

- API key/secret validity
- Registrar account balance
- Monthly budget threshold

### Domain list shows unknown dates

If domain timestamps were written by older versions, records may be missing
parseable date fields. Running future rotations will write normalized values.
