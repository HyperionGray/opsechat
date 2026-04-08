# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation subsystem for burner email workflows.
Current implementation supports:

- registrar API integration via `PorkbunAPIClient`
- budget-aware purchasing via `DomainRotationManager`
- interactive command-line operations via `domain_rotation_cli.py`

This guide documents the currently implemented behavior.

## Supported Registrar

- Porkbun API (`domain_manager.PorkbunAPIClient`)
- Additional registrars can be added by subclassing `DomainAPIClient`

## CLI Setup

1. Get Porkbun API credentials from <https://porkbun.com/account/api>.
2. Configure the CLI:

```bash
python domain_rotation_cli.py config
```

The CLI stores configuration in:

```text
~/.opsechat/domain_config.json
```

The file is written with mode `0600`.

## CLI Commands

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
python domain_rotation_cli.py config
```

### `status`

Shows active domain and current budget state.

### `search`

Performs several attempts to find low-cost available domains.

### `rotate`

Interactive purchase flow:

1. checks remaining monthly budget
2. finds an available domain under budget
3. asks for confirmation
4. purchases and persists state if confirmed

### `list`

Displays owned domains and marks the active domain.

## Persistence and State Model

The CLI persists:

- `current_spending`
- `current_spending_month` (UTC `YYYY-MM`)
- `owned_domains`
- `active_domain`

### Datetime serialization

Owned domain timestamps (`purchased_at`, `expires_at`) are saved as ISO-8601 strings.
On load, the CLI parses ISO strings back to datetime objects and gracefully handles
legacy or malformed values.

### Automatic monthly rollover

When the CLI detects a new UTC month, it automatically resets `current_spending` to
`0.0` and updates `current_spending_month`.

No manual monthly reset is required for spending rollover.

## Python API Usage

If you want non-interactive automation (for cron or scripts), use the Python API
directly instead of the interactive CLI prompt.

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient("YOUR_API_KEY", "YOUR_SECRET")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

# Discover a cheap available domain
domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
if domain_info:
    ok = manager.purchase_domain_if_budget_allows(
        domain_info["domain"],
        domain_info["price"],
    )
    if ok:
        print("Active domain:", manager.get_active_domain())
        print("Budget:", manager.get_budget_status())
```

### Main manager methods

- `generate_random_domain(tld="xyz", length=8)`
- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_domain()`
- `get_active_domain()`
- `get_owned_domains()`
- `get_budget_status()`

## Recommended Operating Pattern

1. Keep monthly budget low and explicit.
2. Use low-cost TLDs (`xyz`, `club`, `online`, `site`, `website`).
3. Run rotation only as frequently as needed.
4. Configure DNS/MX records after successful purchase.
5. Store API keys securely and never commit them.

## Troubleshooting

### API authentication failures

Validate API credentials and test connectivity:

```bash
curl -X POST https://porkbun.com/api/json/v3/ping \
  -H "Content-Type: application/json" \
  -d '{"apikey":"your_api_key","secretapikey":"your_secret_key"}'
```

### No domain found under budget

- increase `max_attempts`
- allow a higher `max_price`
- try again later (registrar inventory/pricing changes)

### Budget appears to reset unexpectedly

Spending resets when the UTC month changes. This is expected behavior.
