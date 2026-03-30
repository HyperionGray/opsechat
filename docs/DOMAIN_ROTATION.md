# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email workflows using
the `domain_manager.py` module and `domain_rotation_cli.py` tool.

Current implementation supports:
- Porkbun API integration
- Cheap TLD discovery (`.xyz`, `.club`, `.online`, `.site`, `.website`)
- Monthly budget enforcement
- Active-domain tracking
- JSON-safe state persistence for CLI usage

## Supported Registrar

- Porkbun (implemented)
- Additional registrars can be added by implementing `DomainAPIClient`

## Configure via Web UI

1. Open `/<secret-path>/email/config`
2. In "Domain API (Porkbun)":
   - Enter API Key
   - Enter API Secret
   - Set monthly budget
3. Click "Configure Domain API"
4. Use "Rotate to New Domain" to purchase and activate a new domain

## Configure via CLI

```bash
python domain_rotation_cli.py config
```

Configuration is stored at:

`~/.opsechat/domain_config.json` (with `0600` file permissions)

The CLI stores runtime state using JSON-safe fields, including ISO-8601
timestamps for purchase and expiration times.

## CLI Commands

```bash
python domain_rotation_cli.py status   # Show current active domain and budget
python domain_rotation_cli.py search   # Probe for cheap available domains
python domain_rotation_cli.py rotate   # Purchase and activate a new domain
python domain_rotation_cli.py list     # List owned domains
```

## Python API (Current)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient("pk1_...", "sk1_...")
manager = DomainRotationManager(api_client=client, monthly_budget=50.0)

# Optional reconfiguration
manager.configure(api_key="pk1_...", secret_key="sk1_...", monthly_budget=25.0)

# Discover and rotate
candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
new_domain = manager.rotate_domain()  # returns str | None

print(manager.get_budget_status())
print(manager.get_config())
```

## State Export/Import

`DomainRotationManager` provides explicit persistence helpers:

```python
state = manager.export_state()   # JSON-serializable dict
manager.import_state(state)      # restores datetimes + numeric fields
```

These methods are used by the CLI to avoid datetime serialization errors.

## Security and Cost Controls

- Purchases are blocked if they exceed configured monthly budget.
- Price values are normalized before comparison/purchase.
- API credentials are never returned by `get_config()`.
- Domain naming uses randomized alphanumeric labels.

## Troubleshooting

### "No API client configured"

Configure credentials first (web config page or `domain_rotation_cli.py config`).

### "Could not find available cheap domain"

Increase `max_attempts`, increase max allowed price, or retry later.

### Budget exceeded

Increase monthly budget in config, or wait until budget policy resets in your
operations process.
