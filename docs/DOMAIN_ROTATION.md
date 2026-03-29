# Domain Rotation Guide

## Overview

OpSecChat includes a built-in domain rotation subsystem for burner email workflows.
It can:

- query random cheap domains from supported TLDs,
- enforce a monthly spend limit,
- purchase and activate a new domain when budget allows,
- expose config/status in both CLI and web route integrations.

Current provider support: **Porkbun** via `PorkbunAPIClient`.

## What changed in this implementation

The domain subsystem now exposes stable integration APIs used by routes and tools:

- `DomainRotationManager.configure(api_key, secret_key, monthly_budget)`
- `DomainRotationManager.get_config()`
- `DomainRotationManager.export_state()` / `load_state()`
- `DomainRotationManager.rotate_domain(return_details=True)` for structured API responses

This aligns the runtime behavior with `email_security_routes.py` and `domain_rotation_cli.py`.

## Configure domain rotation

### Option A: CLI (recommended)

```bash
python domain_rotation_cli.py config
```

This writes local config to:

`~/.opsechat/domain_config.json`

with file mode `0600`.

### Option B: In code

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=10.0,
)
```

## CLI commands

```bash
python domain_rotation_cli.py config   # set API credentials + budget
python domain_rotation_cli.py status   # show active domain and budget
python domain_rotation_cli.py search   # sample cheap available domains
python domain_rotation_cli.py rotate   # purchase + activate next domain
python domain_rotation_cli.py list     # list owned domains
```

## Python API usage

### Check status/config

```python
from domain_manager import domain_rotation_manager

print(domain_rotation_manager.get_config())
print(domain_rotation_manager.get_budget_status())
```

### Rotate with structured response

```python
from domain_manager import domain_rotation_manager

result = domain_rotation_manager.rotate_domain(return_details=True)
if result["success"]:
    print("New domain:", result["domain"])
    print("Price:", result["price"])
else:
    print("Rotation failed:", result["error"])
```

### Rotate with simple response

```python
# Returns domain string on success, None on failure
domain = domain_rotation_manager.rotate_domain()
```

## Web route integration

`email_security_routes.py` uses:

- `domain_rotation_manager.get_config()` for configuration display
- `domain_rotation_manager.configure(...)` for saved settings
- `domain_rotation_manager.rotate_domain(return_details=True)` for API response payloads

So `/.../email/domain/rotate` now consistently returns JSON shaped like:

```json
{
  "success": true,
  "domain": "abcd1234.xyz",
  "price": 2.49,
  "remaining_budget": 7.51
}
```

or

```json
{
  "success": false,
  "error": "Could not find available cheap domain"
}
```

## Budget and safety behavior

- Purchases are blocked if `current_spending + price > monthly_budget`.
- Price parsing accepts registrar values like `"2.99"` or `"$2.99"`.
- Rotation checks remaining budget before attempting search/purchase.

## Security notes

- Never commit API keys.
- Use least-privilege API credentials where provider supports it.
- Rotate keys if leaked.

## Troubleshooting

### "No API client configured"

Configure credentials first:

```bash
python domain_rotation_cli.py config
```

or call `configure(...)` in code.

### Rotation returns budget error

Increase budget in config, or reset spend state if appropriate for your environment.

### No cheap domain found

Try again later; availability/pricing can fluctuate across TLDs.
