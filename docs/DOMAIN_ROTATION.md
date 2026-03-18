# Domain Rotation Guide

## Overview

OpSecChat supports burner-domain rotation through:

- `domain_manager.py` for registrar API logic and budget checks
- `domain_rotation_cli.py` for interactive CLI workflows
- `rotate-domain.py` as a compatibility entrypoint
- `/email/config` and `/email/domain/rotate` in the active web routes

This guide documents the currently supported behavior.

## Configure via CLI

```bash
python domain_rotation_cli.py config
```

Or use the compatibility script:

```bash
python rotate-domain.py config
```

You will be prompted for:

- Porkbun API key
- Porkbun API secret
- Monthly budget (USD)

Configuration is stored at:

`~/.opsechat/domain_config.json`

## CLI Commands

```bash
# Show current budget and active domain
python domain_rotation_cli.py status

# Search for cheap available domains
python domain_rotation_cli.py search

# Purchase and activate a new domain
python domain_rotation_cli.py rotate

# List purchased domains
python domain_rotation_cli.py list
```

The `rotate-domain.py` wrapper supports the same commands.

## Web UI Integration

Domain rotation is integrated in active runtime routes:

- `POST /<path>/email/config` with `action=configure_domain_api`
- `POST /<path>/email/domain/rotate`

When a new domain is rotated successfully:

1. The domain rotation manager updates `active_domain`
2. Burner email manager switches its custom domain
3. New burner addresses use the rotated domain

## Budget and Safety Rules

- Purchases are denied if they exceed the configured monthly budget.
- Domain search prioritizes low-cost TLDs (`.xyz`, `.club`, `.online`, `.site`, `.website`).
- State persistence in CLI now safely serializes purchase timestamps.

## Notes

- Domain purchases are real transactions at your registrar.
- Validate API credentials before running rotation in production.
- Keep API credentials private and never commit them to version control.
