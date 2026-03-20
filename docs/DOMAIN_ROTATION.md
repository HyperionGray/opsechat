# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation module (`domain_manager.py`) and CLI
(`domain_rotation_cli.py`) for purchasing low-cost domains and rotating the
active burner domain while respecting a monthly budget.

## What is Implemented

- Porkbun API client (`PorkbunAPIClient`)
- Budget-aware domain purchasing (`DomainRotationManager`)
- CLI commands for configure/search/rotate/status/list/budget
- Persistent local CLI state in `~/.opsechat/domain_config.json`
- Backward-compatible helper methods for existing scripts:
  - `search_cheap_domains(...)`
  - `rotate_to_new_domain(...)`
  - `generate_random_domain_name(...)`
  - `budget_manager` compatibility accessor

## CLI Usage

### 1) Configure credentials

```bash
python domain_rotation_cli.py config
```

### 2) Search candidates without purchasing

```bash
python domain_rotation_cli.py search --max-price 3.0 --attempts 12 --results 5
```

### 3) Rotate domain interactively

```bash
python domain_rotation_cli.py rotate --max-price 3.0 --attempts 12
```

### 4) Rotate domain non-interactively (automation-friendly)

```bash
python domain_rotation_cli.py rotate --yes --max-price 3.0 --attempts 12
```

### 5) Check status and owned domains

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

### 6) Set monthly budget

```bash
python domain_rotation_cli.py budget --set 25
```

## Python API Usage

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.set_monthly_budget(25.0)
candidates = domain_rotation_manager.search_cheap_domains(
    max_price=3.0,
    max_attempts=10,
    limit=5,
)
print(candidates)

result = domain_rotation_manager.rotate_to_new_domain(
    max_price=3.0,
    max_attempts=10,
)
print(result)
```

## Notes

- The CLI stores state in JSON and now serializes/restores datetime fields
  safely for `owned_domains`.
- Budget guardrails are enforced before purchases.
- The module currently ships with Porkbun support; additional registrars can be
  added by implementing `DomainAPIClient`.
