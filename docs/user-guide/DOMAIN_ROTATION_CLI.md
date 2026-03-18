# Domain Rotation CLI

## Overview

`domain_rotation_cli.py` manages burner-email domain rotation through registrar APIs (currently Porkbun). It provides:

- credential setup
- cheap-domain search
- budget-aware domain purchase/rotation
- persistent state for owned domains and current active domain

State is stored in:

`~/.opsechat/domain_config.json`

The file is written with `0600` permissions.

## Configure Credentials

```bash
python domain_rotation_cli.py config
```

You will be prompted for:

- Porkbun API key
- Porkbun API secret
- monthly budget in USD

## Commands

### Show Status

```bash
python domain_rotation_cli.py status
```

Shows active domain, spending, and budget remaining.

### Search for Cheap Domains

```bash
python domain_rotation_cli.py search
```

Optional tuning:

```bash
python domain_rotation_cli.py search --max-price 3.00 --attempts 10
```

### Rotate to a New Domain

```bash
python domain_rotation_cli.py rotate
```

Optional tuning:

```bash
python domain_rotation_cli.py rotate --max-price 2.50
```

Automation/non-interactive mode:

```bash
python domain_rotation_cli.py rotate --yes
```

### List Owned Domains

```bash
python domain_rotation_cli.py list
```

This reads persisted records and formats purchase/expiry dates from stored ISO timestamps.

## Persistence Behavior

After successful purchases, the CLI persists:

- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains` (with ISO datetime fields)

On startup, stored state is reloaded and converted back into runtime objects.

## Notes

- Purchases are denied when monthly budget would be exceeded.
- Prices from registrar responses are normalized (e.g. `$2.49` to `2.49`).
- Use a low `--max-price` value to constrain rotation cost in automation.
