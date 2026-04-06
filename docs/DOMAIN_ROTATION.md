# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation system for burner email operations.
The implementation consists of:

- `domain_manager.py`: registrar client and rotation logic
- `domain_rotation_cli.py`: operator-friendly CLI

The current registrar integration is Porkbun.

## What Is Implemented

### Domain Manager (`domain_manager.py`)

- Registrar abstraction via `DomainAPIClient`
- Porkbun integration via `PorkbunAPIClient`
- Rotation and budget control via `DomainRotationManager`

`DomainRotationManager` supports:

- Random domain generation (`generate_random_domain`)
- Cheap domain search (`find_cheap_available_domain`)
- Budget-checked purchase (`purchase_domain_if_budget_allows`)
- Domain rotation (`rotate_domain`)
- Active/owned domain state (`get_active_domain`, `get_owned_domains`)
- Budget status reporting (`get_budget_status`)

### CLI (`domain_rotation_cli.py`)

Supported commands:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Quick Start

### 1) Configure API credentials

```bash
python domain_rotation_cli.py config
```

This stores local config at:

`~/.opsechat/domain_config.json`

File permissions are restricted to owner-only (`0600`).

### 2) Check current status

```bash
python domain_rotation_cli.py status
```

### 3) Search for low-cost domains

```bash
python domain_rotation_cli.py search
```

### 4) Rotate to a new domain

```bash
python domain_rotation_cli.py rotate
```

### 5) List purchased domains

```bash
python domain_rotation_cli.py list
```

## State Persistence Behavior

The CLI persists runtime state in the same config file:

- `current_spending`
- `active_domain`
- `owned_domains`

Each domain entry includes:

- `domain`
- `price`
- `purchased_at`
- `expires_at`

Timestamp fields are serialized as ISO-8601 strings in JSON and converted back
to `datetime` objects when loading state.

This makes state portable and prevents JSON serialization errors when saving.

## API Credential Setup (Porkbun)

1. Create or sign in to your Porkbun account.
2. Open account API settings.
3. Generate API key + secret.
4. Run `python domain_rotation_cli.py config` and enter values.

Reference:

- https://porkbun.com/api/json/v3/documentation

## Budget and Safety

- Purchases are blocked when they exceed configured monthly budget.
- Domain search prioritizes lower-cost TLDs.
- CLI requests explicit confirmation before purchase.

## Test Coverage

Relevant tests:

- `tests/test_domain_manager.py`
- `tests/test_domain_rotation_cli.py`

They cover manager behavior, CLI state serialization/deserialization, and date handling.

## Operational Notes

- Domain purchasing has side effects (real charges) when valid credentials/funds are configured.
- Use low limits first and verify budget output before rotation.
- Keep registrar API credentials private and rotate them periodically.
