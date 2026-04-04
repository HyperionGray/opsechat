# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation system for burner email workflows. It can:

- search for cheap available domains,
- buy a domain within budget,
- track owned domains locally, and
- keep a currently active domain for burner usage.

Current registrar support: Porkbun (`PorkbunAPIClient`).

## What is implemented

The production implementation lives in:

- `domain_manager.py`
- `domain_rotation_cli.py`

Core manager methods:

- `find_cheap_available_domain(max_price=5.0, max_attempts=10)`
- `purchase_domain_if_budget_allows(domain, price)`
- `rotate_domain()`
- `get_budget_status()`
- `export_state()` and `import_state()` for JSON-safe persistence
- `cleanup_expired_domains()` for local record maintenance

## CLI usage

The CLI stores config and state at:

`~/.opsechat/domain_config.json`

### Configure credentials and budget

```bash
python domain_rotation_cli.py config
```

### Show current status

```bash
python domain_rotation_cli.py status
```

### Search for cheap domains

```bash
python domain_rotation_cli.py search
```

### Rotate to a newly purchased domain

```bash
python domain_rotation_cli.py rotate
```

### List owned domains

```bash
python domain_rotation_cli.py list
```

### Prune expired local records

```bash
python domain_rotation_cli.py cleanup
```

## Persistence model

State persistence is local and JSON-based. Datetime fields are serialized as ISO8601 strings and restored on load.

Saved state includes:

- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains` with:
  - `domain`
  - `price`
  - `purchased_at`
  - `expires_at`

## Budget behavior

- Purchases are blocked when `current_spending + price > monthly_budget`.
- Budget values are tracked locally in CLI state.
- Budget reset policy is operational (you decide when to reset monthly counters).

## Operational recommendations

- Use cheaper TLDs for rotation (`.xyz`, `.club`, `.online`, `.site`, `.website`).
- Run `status` or `cleanup` periodically to keep local state clean.
- Keep Porkbun API keys out of git and rotate them periodically.
- Validate registrar account balance before automation runs.

## Troubleshooting

### "Could not find available cheap domain"

- Increase `max_attempts` in custom scripts.
- Increase `max_price`.
- Retry later; registrar availability fluctuates.

### "Budget exceeded"

- Increase configured monthly budget via CLI `config`.
- Wait for your next budget cycle and reset counters operationally.

### Local state looks stale

- Run:

```bash
python domain_rotation_cli.py cleanup
python domain_rotation_cli.py status
```

This removes expired local records and re-evaluates the active domain.
