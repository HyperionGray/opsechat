# Domain Rotation Guide

## Overview

OpSechat includes a domain rotation system used by burner email workflows.
This guide documents the currently implemented APIs and CLI behavior.

## Implemented Providers

- **Porkbun**: fully supported for search/purchase/pricing/listing.
- **Namecheap**: client implemented with XML API support (`check`, `pricing`, `create`), but purchasing requires a configured contact profile ID.

## Core API (`domain_manager.py`)

### Configure a provider

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_xxx",
    secret_key="sk1_xxx",
    monthly_budget=50.0,
    provider="porkbun",
)
```

Namecheap configuration:

```python
domain_rotation_manager.configure(
    api_key="namecheap_api_key",
    monthly_budget=50.0,
    provider="namecheap",
    username="namecheap_username",
    client_ip="1.2.3.4",
    contact_profile_id="123456",  # required for purchases
    sandbox=True,
)
```

### Rotate and inspect state

```python
result = domain_rotation_manager.rotate_domain_result()
if result["success"]:
    print("New active domain:", result["domain"])
else:
    print("Rotation failed:", result["error"])

print(domain_rotation_manager.get_budget_status())
print(domain_rotation_manager.get_config())
```

### JSON-safe persistence

`DomainRotationManager` now supports JSON-safe state export/import:

```python
state = domain_rotation_manager.serialize_state()
# persist `state` in JSON, then later:
domain_rotation_manager.load_state(state)
```

This serializes `purchased_at` / `expires_at` timestamps to ISO strings and restores them when loading.

## CLI (`domain_rotation_cli.py`)

Commands:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

What changed:

- CLI config stores provider credentials under `providers`.
- Active provider is tracked via `active_provider`.
- Runtime state is saved under `manager_state` using manager serialization APIs.
- `list` handles ISO timestamp values safely.
- Legacy top-level keys (`api_key`, `api_secret`) are migrated automatically if present.

## Web config integration

`/email/config` now uses implemented actions from `templates/email_config.html`:

- `configure_smtp`
- `configure_imap`
- `configure_domain_api`

And it now supports:

- `POST /<path>/email/receive` to fetch IMAP messages and store them in the user inbox.
- `POST /<path>/email/domain/rotate` to rotate/purchase a domain and show a status message.

## Notes

- Domain purchases are real and can incur registrar charges.
- Keep API credentials out of version control.
- Start with a low monthly budget and monitor `get_budget_status()`.
