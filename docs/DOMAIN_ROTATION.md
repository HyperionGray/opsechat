# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation subsystem for burner-email operations. It can:

- Check registrar availability for random domains
- Enforce a monthly budget
- Purchase and rotate to a new active domain
- Persist CLI state safely between runs

The current registrar client is **Porkbun**.

---

## Quick Start (CLI)

```bash
# Configure credentials + budget
python domain_rotation_cli.py config

# Check status
python domain_rotation_cli.py status

# Search for cheap candidates
python domain_rotation_cli.py search

# Buy + rotate
python domain_rotation_cli.py rotate

# List purchased domains
python domain_rotation_cli.py list
```

Config file location:

```text
~/.opsechat/domain_config.json
```

The CLI now stores timestamps in JSON-safe format and restores them on load.

---

## Python API

### Core classes

- `DomainAPIClient` (abstract base class)
- `PorkbunAPIClient` (registrar implementation)
- `DomainRotationManager` (budget + rotation state)

### Basic usage

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=20.0)
manager.configure(api_key="pk1_...", secret_key="sk1_...", monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=3.0, max_attempts=10)
print(candidate)

result = manager.rotate_domain(return_details=True)
print(result)  # {"success": True/False, ...}
```

### Config/status helpers

```python
config = manager.get_config()
status = manager.get_budget_status()
```

`get_config()` returns safe fields (masked API key, budget info, active domain, etc.).

`get_budget_status()` includes:

- `monthly_budget`
- `current_spending`
- `remaining`
- `domains_owned`
- `spending_month` (`YYYY-MM`)

---

## Monthly Budget Behavior

Spending is tracked per month (`YYYY-MM`).  
When a new month starts, the manager automatically resets:

- `current_spending` -> `0.0`
- `spending_month` -> current month

This happens automatically during status checks and purchase flows.

---

## State Persistence

The manager supports explicit state import/export:

```python
state = manager.export_state()
manager.import_state(state)
```

`export_state()` is JSON-serializable (datetimes are ISO-8601 strings).  
`import_state()` accepts those serialized strings and restores datetime objects internally.

---

## Security Notes

- Do **not** commit API keys.
- Use dedicated API credentials for this workflow.
- Keep budgets conservative and monitor purchase history.
- Treat active burner domains as sensitive operational metadata.

---

## Troubleshooting

### "No API client configured"

Run:

```bash
python domain_rotation_cli.py config
```

### "Could not find available cheap domain"

Increase attempts or price cap:

```python
manager.find_cheap_available_domain(max_price=5.0, max_attempts=25)
```

### Purchase denied by budget

Check:

```python
print(manager.get_budget_status())
```

Increase budget only if appropriate for your threat model and ops constraints.
