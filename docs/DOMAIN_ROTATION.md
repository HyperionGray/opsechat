# Domain Rotation Guide

## Overview

OpSecChat supports managed burner-domain rotation for email workflows. The domain manager can:

- Configure Porkbun API credentials and budget limits
- Search for low-cost available domains
- Purchase/activate a new domain when budget allows
- Track spending by month
- Return structured rotation results for web/API handlers

## Quick Start

### Web UI (recommended)

1. Open:

   `http://<onion-host>/<random-path>/email/config`

2. In **Domain API (Porkbun)**:
   - Enter API key and secret
   - Set a monthly budget
   - Click **Configure Domain API**

3. Click **Rotate to New Domain** to find and purchase the next available low-cost domain.

4. Use **Budget Status** in the same page to track spending and remaining budget.

### CLI

Use the helper CLI for manual domain operations:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Runtime Behavior

### Budget and monthly reset

- Spending is tracked against a monthly budget.
- The tracked spending period resets automatically when a new UTC month begins.

### Rotation flow

Rotation uses this sequence:

1. Generate random domain candidates (cheap TLD priority)
2. Check registrar availability
3. Filter by price threshold
4. Purchase if the configured budget allows
5. Promote the purchased domain to active domain

### State persistence (CLI)

`domain_rotation_cli.py` stores manager state in:

`~/.opsechat/domain_config.json`

The manager now serializes datetime fields to ISO format and normalizes them on load, so `list` and `status` remain stable across process restarts.

## API/Developer Notes

`DomainRotationManager` exposes helpers used by routes:

- `configure(api_key, secret_key, monthly_budget)`
- `get_config()`
- `get_budget_status()`
- `rotate_domain_with_details(max_price=5.0)`
- `export_state()` / `import_state(state)`

Example:

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
    monthly_budget=25.0,
)

result = domain_rotation_manager.rotate_domain_with_details(max_price=4.0)
if result["success"]:
    print("Active domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

## Route Integration

The active email routes now support:

- `POST /<path>/email/config` with actions:
  - `configure_smtp`
  - `configure_imap`
  - `configure_domain_api`
- `POST /<path>/email/domain/rotate`
- `POST /<path>/email/receive`

This matches the forms in `templates/email_config.html`.

## Security Notes

- Credentials are held in memory at runtime.
- Do not commit registrar credentials.
- Keep budgets conservative and monitor registrar billing dashboards.
- Use low-cost TLDs for short-lived burner operations.

## Troubleshooting

### "Domain configuration failed"

- Confirm API key and secret
- Confirm Porkbun API access is enabled
- Confirm budget value is numeric and greater than zero

### "No available domain found within budget constraints"

- Increase max domain price (if operationally acceptable)
- Retry later if registrar queries are being rate-limited
- Increase monthly budget when current spending is near the limit

### "Fetched 0 email(s) from IMAP"

- Validate IMAP configuration first
- Confirm mailbox has matching unread/all messages based on filter
