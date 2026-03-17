# Domain Rotation Guide

## Overview

Opsechat supports automated burner-domain rotation with budget controls and multiple registrar backends.

Supported providers in code:

- **Porkbun** (`PorkbunAPIClient`)
- **Namecheap** (`NamecheapAPIClient`)

The central orchestrator is `DomainRotationManager`.

## CLI usage

Configure credentials:

```bash
python domain_rotation_cli.py config
```

Search cheap domains (optionally pin provider):

```bash
python domain_rotation_cli.py search
python domain_rotation_cli.py search --provider porkbun
python domain_rotation_cli.py search --provider namecheap
```

Rotate to a newly purchased domain:

```bash
python domain_rotation_cli.py rotate
python domain_rotation_cli.py rotate --provider namecheap
```

Inspect state:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

## Python API usage

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=25.0)

# Configure Porkbun
manager.configure(
    provider="porkbun",
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
)

# Configure Namecheap as an additional provider
manager.configure(
    provider="namecheap",
    api_key="namecheap_key",
    username="namecheap_user",
    client_ip="203.0.113.10",
    sandbox=True,  # optional
)

result = manager.rotate_to_new_domain(max_price=5.0)
if result["success"]:
    print("New domain:", result["domain"], "provider:", result["provider"])
else:
    print("Rotation failed:", result["error"])
```

## State persistence

`DomainRotationManager` now includes safe JSON state helpers:

- `export_state()` for serializable persistence
- `import_state(state)` to restore

This avoids raw `datetime` objects in JSON and is used by `domain_rotation_cli.py`.

## Notes

- Namecheap purchases require a contact profile for required registration fields.
- Budget limits are enforced before purchase attempts.
- Provider-aware rotation records which registrar purchased each domain.
