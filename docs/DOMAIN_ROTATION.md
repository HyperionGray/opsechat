# Domain Rotation Guide

## Overview

OpSecChat supports automated burner-email domain rotation through Porkbun API integration.  
The current implementation focuses on safe purchasing with budget limits, lightweight state persistence, and simple operational flows for both CLI and web routes.

## What is implemented

- `DomainRotationManager` supports:
  - Random candidate generation on low-cost TLDs
  - Availability checks via `DomainAPIClient`
  - Budget-aware purchasing (`purchase_domain_if_budget_allows`)
  - Rotation flow (`rotate_domain`, `rotate_domain_with_result`)
  - JSON-safe state export/import (`export_state`, `load_state`)
  - Automatic monthly budget rollover (period-based spending reset)
- `domain_rotation_cli.py` supports:
  - `config`, `status`, `search`, `rotate`, `list`
  - Safe persistence under `~/.opsechat/domain_config.json`
- Web integration endpoint:
  - `POST /<path>/email/domain/rotate` returns JSON result payload

## Setup

### 1) Get Porkbun API credentials

1. Sign up at [porkbun.com](https://porkbun.com)
2. Go to Account -> API Access
3. Enable API access
4. Save:
   - API key
   - Secret API key

### 2) Configure via CLI

```bash
python domain_rotation_cli.py config
```

You will be prompted for:
- API key
- API secret
- monthly budget

### 3) Configure via web UI

Open `/<secret-path>/email/config` and fill:
- Porkbun API key
- Porkbun API secret
- monthly budget

## CLI usage

```bash
# Show status and budget
python domain_rotation_cli.py status

# Search for candidate cheap domains
python domain_rotation_cli.py search

# Rotate to a newly purchased domain
python domain_rotation_cli.py rotate

# List owned domains
python domain_rotation_cli.py list
```

## Programmatic usage

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("pk_xxx", "sk_xxx")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

result = manager.rotate_domain_with_result()
if result["success"]:
    print("New active domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

## State persistence format

`DomainRotationManager.export_state()` returns JSON-safe state:

```json
{
  "current_spending": 3.98,
  "monthly_budget": 20.0,
  "owned_domains": [
    {
      "domain": "abcd1234.xyz",
      "price": 1.99,
      "purchased_at": "2026-04-08T12:00:00Z",
      "expires_at": "2027-04-08T12:00:00Z"
    }
  ],
  "active_domain": "abcd1234.xyz",
  "spending_period": "2026-04"
}
```

This is intentionally compatible with `json.dump` without custom encoders.

## Budget and safety behavior

- Purchases are denied when `current_spending + price > monthly_budget`
- Invalid/unknown prices are rejected safely
- Spending resets automatically when month changes (`YYYY-MM` period rollover)
- `rotate_domain_with_result` returns explicit failure reasons

## Troubleshooting

### API request failures

Validate API credentials and connectivity:

```bash
curl -X POST https://porkbun.com/api/json/v3/ping \
  -H "Content-Type: application/json" \
  -d '{"apikey":"your_api_key","secretapikey":"your_secret_key"}'
```

### Rotation returns no candidate

- Raise budget threshold for testing
- Retry (candidate generation is randomized)
- Confirm API availability checks are returning price + availability

### Budget appears "stuck"

`spending_period` drives rollover. If you import old state, `load_state` normalizes period and resets spending automatically when needed.
