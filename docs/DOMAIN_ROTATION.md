# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation manager for burner-email workflows. It can:

- check for inexpensive available domains,
- purchase domains through Porkbun,
- enforce a monthly spend cap,
- track active/owned domains in memory.

## Safety Notes

- Domain purchases are **real purchases** that charge your registrar account.
- API credentials should never be committed to git.
- Rotation state is designed for ephemeral runtime use unless you explicitly persist it via the CLI config file.

## Current Supported Registrar

- **Porkbun** via `PorkbunAPIClient`

Additional registrars can be added by extending `DomainAPIClient`.

---

## Web UI Configuration (`/email/config`)

The Email Configuration page supports domain settings:

1. Set Porkbun API key and secret.
2. Set monthly budget (USD).
3. Save configuration.
4. Use the "Rotate to New Domain" button to purchase and activate a new domain.

The page displays:

- active domain,
- monthly budget,
- current spending,
- remaining budget,
- number of owned domains.

---

## CLI Usage

Use `domain_rotation_cli.py` for local/operator workflows:

```bash
python domain_rotation_cli.py config   # Configure API credentials + budget
python domain_rotation_cli.py status   # Show active domain and budget
python domain_rotation_cli.py search   # Search for cheap available domains
python domain_rotation_cli.py rotate   # Purchase and activate a new domain
python domain_rotation_cli.py list     # List owned domains
```

Config is stored at:

`~/.opsechat/domain_config.json`

with file permissions set to `0600`.

---

## Python API Reference

### Configure Manager

```python
from domain_manager import domain_rotation_manager

result = domain_rotation_manager.configure(
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=25.0,
)
print(result)  # {"success": True, ...}
```

### Rotate Domain (Structured Result)

```python
result = domain_rotation_manager.rotate_domain_with_result()
if result["success"]:
    print("Active domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])
```

### Rotate Domain (Backward-Compatible String Return)

```python
new_domain = domain_rotation_manager.rotate_domain()
if new_domain:
    print("Active domain:", new_domain)
```

### Budget / Status

```python
status = domain_rotation_manager.get_budget_status()
print(status)

config = domain_rotation_manager.get_config()
print(config["configured"], config["api_key_masked"])
```

---

## Troubleshooting

### "No API client configured"

Configure credentials first via:

- Web UI (`/email/config`), or
- `python domain_rotation_cli.py config`

### "Monthly budget exhausted"

Increase budget or wait for your operational reset policy, then retry rotation.

### Domain search returns no result

Try again later with higher max price/budget. Low-cost TLD inventory can vary.

---

## Implementation Notes

- Core module: `domain_manager.py`
- CLI wrapper: `domain_rotation_cli.py`
- Web integration routes: `email_security_routes.py`
- Tests: `tests/test_domain_manager.py`
