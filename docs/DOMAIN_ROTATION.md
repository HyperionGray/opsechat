# Domain Rotation Guide

## Overview

OpSecChat supports rotating burner-email domains through registrar APIs with a monthly budget guardrail.

Current implementation includes:

- Registrar client: Porkbun (`PorkbunAPIClient`)
- Rotation engine: `DomainRotationManager`
- Operator CLI: `domain_rotation_cli.py`
- Web configuration actions: `/email/config` and `/email/domain/rotate`

## CLI Usage

The CLI stores configuration at:

`~/.opsechat/domain_config.json`

Available commands:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Configure API credentials

```bash
python domain_rotation_cli.py config
```

This prompts for:

- Porkbun API key
- Porkbun API secret
- Monthly budget (USD)

### Search for low-cost domains

```bash
python domain_rotation_cli.py search
```

This performs multiple search attempts and prints candidates under the current price threshold.

### Rotate to a new domain

```bash
python domain_rotation_cli.py rotate
```

The CLI will:

1. Show current budget status
2. Find an available low-cost candidate
3. Ask for confirmation
4. Purchase (if approved and within budget)
5. Persist updated state

### List purchased domains

```bash
python domain_rotation_cli.py list
```

Outputs owned domains, active marker, and purchase/expiry timestamps.

## Persisted State

The CLI now persists runtime state using a structured `state` block:

```json
{
  "api_key": "pk_...",
  "api_secret": "sk_...",
  "monthly_budget": 50.0,
  "state": {
    "monthly_budget": 50.0,
    "current_spending": 3.98,
    "active_domain": "abc123.xyz",
    "owned_domains": [
      {
        "domain": "abc123.xyz",
        "price": 1.99,
        "purchased_at": "2026-03-14T10:30:00",
        "expires_at": "2027-03-14T10:30:00"
      }
    ]
  }
}
```

Notes:

- Datetimes are stored as ISO-8601 strings.
- Legacy flat keys (`current_spending`, `owned_domains`, `active_domain`) are still read for backward compatibility.
- On save, legacy flat keys are migrated into `state`.

## Web Configuration Flow

`/email/config` supports:

- SMTP configuration (`configure_smtp`)
- IMAP configuration (`configure_imap`)
- Domain API configuration (`configure_domain_api`)
- IMAP fetch action (`/email/receive`)
- Domain rotation action (`/email/domain/rotate`)

When a rotation succeeds through the web form, the new domain is also set as the burner default domain.

## Security and Operations Notes

- Budget checks run before purchase to prevent overspending.
- API credentials are held in runtime memory and config file storage; protect the file with strict permissions.
- Domain search prefers inexpensive TLDs: `.xyz`, `.club`, `.online`, `.site`, `.website`.

## Related Files

- `domain_manager.py`
- `domain_rotation_cli.py`
- `email_routes.py`
- `docs/setup/DOMAIN_API_SETUP.md`
