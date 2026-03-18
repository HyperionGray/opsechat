# Domain Rotation Guide

## Overview

OpSecChat supports automated burner-domain rotation using registrar APIs.
The current implementation includes:

- A `PorkbunAPIClient` with retry and exponential backoff
- A `DomainRotationManager` for search, purchase, rotation, and budget tracking
- A `domain_rotation_cli.py` tool for operator workflows

This guide documents the API as it exists today.

## Features

- Search for low-cost available domains
- Purchase a domain only when within monthly budget
- Rotate active burner domain in one call
- Retry transient registrar failures (network, 429, 5xx)
- Persist CLI state safely (including purchase/expiry timestamps)

## Python API

### Configure manager from credentials

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
config = manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
    monthly_budget=15.0,
    retry_attempts=3,
    backoff_base_seconds=0.5,
)
print(config)
```

`get_config()` returns route-safe metadata:

```python
{
  "configured": True,
  "registrar": "porkbun",
  "api_key_masked": "********1234",
  "monthly_budget": 15.0,
  "current_spending": 0.0,
  "remaining_budget": 15.0,
  "active_domain": None,
  "domains_owned": 0,
  "retry_attempts": 3,
  "backoff_base_seconds": 0.5
}
```

### Search for cheap domains (no purchase)

```python
results = manager.search_cheap_domains(
    tlds=["xyz", "club"],
    max_price=3.0,
    limit=5,
)
for item in results:
    print(item["domain"], item["price"], item["currency"])
```

### Rotate to a new domain (structured result)

```python
result = manager.rotate_to_new_domain(max_price=5.0)
if result["success"]:
    print("New active domain:", result["domain"])
    print("Price:", result["price"])
    print("Remaining budget:", result["remaining_budget"])
else:
    print("Rotation failed:", result["error"])
```

For legacy callers, `rotate_domain()` still returns only the domain string (or `None`).

## Retry / Backoff behavior

The Porkbun client retries transient failures:

- HTTP `429` (rate limited)
- HTTP `5xx`
- connection and timeout errors
- transient invalid JSON payloads

Backoff is exponential:

- attempt 1 delay: `base * 2^0`
- attempt 2 delay: `base * 2^1`
- attempt 3 delay: `base * 2^2`

Example with base `0.5` seconds: `0.5s`, `1.0s`, `2.0s`.

## CLI usage

### Configure credentials and retry settings

```bash
python domain_rotation_cli.py config
```

The config command now stores:

- API key and secret
- monthly budget
- retry attempts
- backoff base seconds

### Check status

```bash
python domain_rotation_cli.py status
```

### Search and rotate

```bash
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## CLI persistence details

`domain_rotation_cli.py` stores state in:

`~/.opsechat/domain_config.json`

Domain records are serialized with ISO-8601 timestamps. On load, timestamps are
parsed back into `datetime` objects so `list` output remains stable across runs.

## Budget guardrails

- Purchases are denied when the monthly budget would be exceeded
- Spending is tracked in `current_spending`
- `get_budget_status()` returns remaining budget and domain count

## Troubleshooting

### "No API credentials configured"

Run:

```bash
python domain_rotation_cli.py config
```

### Rotation fails with budget error

Increase monthly budget in config, or reduce max price for searches.

### Registrar API intermittently fails

Increase retry attempts and/or backoff base in CLI config.

## Security notes

- Never commit registrar API keys to git
- Keep local config file permissions restrictive (`0600` is applied by CLI)
- Prefer dedicated scoped API keys where registrar supports it
