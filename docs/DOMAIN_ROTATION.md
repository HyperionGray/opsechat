# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows. The current implementation provides:

- Porkbun registrar integration via `PorkbunAPIClient`
- Budget-aware purchasing with monthly spending caps
- Runtime domain rotation in the email config route
- Stateful CLI persistence in `~/.opsechat/domain_config.json`

## Current API Surface

The active manager is `domain_rotation_manager` from `domain_manager.py`.

Supported methods:

- `configure(api_key, secret_key, monthly_budget=50.0)`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_domain()`
- `get_budget_status()`
- `get_active_domain()`
- `get_owned_domains()`
- `get_config()`
- `export_state()` and `import_state(state)`

## Configure Through Web UI

1. Start OpSecChat.
2. Open:

```text
http://<your-host>/<secret-path>/email/config
```

3. In the Domain API section:
   - Enter Porkbun API key
   - Enter Porkbun API secret
   - Set monthly budget
4. Submit **Configure Domain API**.
5. Use **Rotate to New Domain** to purchase and activate a new domain.

When rotation succeeds, the burner manager custom domain is updated for newly generated burner addresses.

## CLI Workflow

Use `domain_rotation_cli.py`:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Persistence Behavior

CLI state is persisted in:

```text
~/.opsechat/domain_config.json
```

Persisted fields include:

- API credentials
- Monthly budget
- Active domain
- Current spending
- Owned domains with purchase and expiry timestamps
- Current budget period (`YYYY-MM`)

Owned domain timestamps are serialized to ISO 8601 and restored on load.

## Budget Model

- Budget period is monthly (`YYYY-MM`, UTC).
- Spending resets automatically when a new month starts.
- Purchases are denied when `current_spending + price > monthly_budget`.

Status comes from `get_budget_status()`:

- `monthly_budget`
- `current_spending`
- `remaining`
- `domains_owned`
- `budget_period`

## Example: Programmatic Usage

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=20.0)
manager.configure("pk1_example", "sk1_example", monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=5)
if candidate:
    purchased = manager.purchase_domain_if_budget_allows(
        candidate["domain"], candidate["price"]
    )
    if purchased:
        print("Active domain:", manager.get_active_domain())
        print(manager.get_budget_status())
```

## Troubleshooting

### "No API client configured"

Configure credentials through `/email/config` or `domain_rotation_cli.py config`.

### "Budget exceeded"

- Increase monthly budget
- Wait for next monthly period reset
- Check status with `domain_rotation_cli.py status`

### "Could not find available cheap domain"

- Retry with additional attempts
- Increase max price threshold slightly
- Verify network/API access

## Notes

- API keys should not be committed to version control.
- Registrar pricing changes frequently; keep budget limits conservative.
- This guide documents implemented behavior only.
