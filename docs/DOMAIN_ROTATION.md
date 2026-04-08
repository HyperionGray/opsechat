# Domain Rotation Guide

## Overview

OpSecChat includes a supported domain rotation workflow for burner email infrastructure:

- `domain_manager.py` provides the registrar API client and rotation logic
- `domain_rotation_cli.py` provides an operator-facing CLI for configuring, searching, rotating, and listing domains

Current registrar support:

- Porkbun (`PorkbunAPIClient`)

The current implementation is intentionally minimal and production-oriented: it supports cheap domain discovery, budget limits, safe state persistence, and explicit operator confirmation before purchase.

## CLI Commands

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Setup

### 1) Obtain Porkbun API credentials

1. Sign in to https://porkbun.com
2. Open Account -> API Access
3. Create API credentials
4. Store your API key and secret key securely

### 2) Configure CLI

```bash
python domain_rotation_cli.py config
```

The CLI stores configuration in:

- `~/.opsechat/domain_config.json`

File permissions are set to `0600` automatically.

## State Persistence Behavior

The CLI persists state after successful purchases. Saved fields include:

- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains`
- `state_version`

Owned domain timestamps are persisted in ISO-8601 format and deserialized when loaded.

Backward compatibility is included for legacy state payloads:

- numeric values stored as strings (e.g. `"$5.25"`)
- older `owned_domains` entries represented as plain strings

## Purchase Flow

`rotate` performs the following:

1. Loads API credentials and persisted state
2. Prints budget status
3. Searches for a cheap available domain (default max: min(5.0, remaining budget))
4. Prompts for explicit `yes` confirmation
5. Purchases the domain only if budget allows
6. Persists updated state

## Output Stability and Safety

The CLI includes output normalization for operational reliability:

- Currency values are printed with two decimal places
- Persisted datetime values are accepted as both `datetime` objects and strings
- List/status output remains stable even with legacy config formats

## Budget Controls

Budget enforcement is performed before purchase:

- Denies purchase when `current_spending + domain_price > monthly_budget`
- Tracks cumulative monthly spending in persisted CLI state

If the registrar returns unexpected price formatting (currency symbols, commas), prices are parsed safely before comparison.

## Example Workflow

```bash
# 1) Configure once
python domain_rotation_cli.py config

# 2) Review current state
python domain_rotation_cli.py status

# 3) Search for candidates
python domain_rotation_cli.py search

# 4) Rotate to a newly purchased domain
python domain_rotation_cli.py rotate

# 5) Verify active domain and history
python domain_rotation_cli.py list
```

## Testing

Related tests:

- `tests/test_domain_manager.py`
- `tests/test_domain_rotation_cli.py`

Run:

```bash
python3 -m pytest tests/test_domain_manager.py tests/test_domain_rotation_cli.py
```
