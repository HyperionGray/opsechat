# Domain Rotation Guide

## Overview

OpSecChat supports burner-email domain rotation using registrar APIs.
The current implementation includes:

- `DomainRotationManager` for search, purchase, and budget enforcement
- `PorkbunAPIClient` for Porkbun API integration
- `domain_rotation_cli.py` for operational CLI workflows

## What Is Implemented

### Core capabilities

- Search for available low-cost domains on common low-cost TLDs
- Purchase domains through registrar API
- Track owned domains and active domain
- Enforce monthly budget limits

### State persistence (CLI)

`domain_rotation_cli.py` persists state in:

`~/.opsechat/domain_config.json`

Saved state includes:

- API credentials (if configured)
- Monthly budget
- Current monthly spending
- Owned domains (with purchase and expiration timestamps)
- Active domain

Timestamps are serialized as ISO 8601 strings and restored on load.

### Monthly budget reconciliation

Monthly spending is recalculated from owned-domain purchase timestamps.
This avoids stale totals across process restarts and month boundaries.

## CLI Usage

### Configure credentials and budget

```bash
python domain_rotation_cli.py config
```

### Show current status

```bash
python domain_rotation_cli.py status
```

### Search for domains

```bash
python domain_rotation_cli.py search
python domain_rotation_cli.py search --max-price 3.00 --attempts 10
```

### Rotate to a new domain

```bash
python domain_rotation_cli.py rotate
python domain_rotation_cli.py rotate --max-price 2.50
```

### List owned domains

```bash
python domain_rotation_cli.py list
```

## Programmatic Usage

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient(api_key="...", api_secret="...")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=3.0, max_attempts=10)
if candidate:
    ok = manager.purchase_domain_if_budget_allows(candidate["domain"], candidate["price"])
    if ok:
        print("Active domain:", manager.get_active_domain())
```

## Notes

- Purchasing domains will charge the registrar account.
- Keep API credentials out of git and local plaintext sharing channels.
- Use small monthly budgets until registrar settings and workflow are verified.
