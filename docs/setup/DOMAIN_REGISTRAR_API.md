# Domain Registrar API Guide

This guide covers registrar integration for automated burner-domain rotation.

## Supported registrars

Opsechat currently supports:

- **Porkbun** (JSON API)
- **Namecheap** (XML API)

The implementation lives in:

- `domain_manager.py`
  - `PorkbunAPIClient`
  - `NamecheapAPIClient`
  - `DomainRotationManager` (registrar-aware fallback search/purchase)
- `domain_rotation_cli.py` (interactive config and operations)

## Quick start (CLI)

Configure credentials:

```bash
python domain_rotation_cli.py config
```

Then run:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

The CLI stores configuration in:

```text
~/.opsechat/domain_config.json
```

with restrictive file permissions (`0600`).

## Registrar-specific notes

### Porkbun

Get credentials from:

- <https://porkbun.com/account/api>

Required values:

- API key
- API secret

### Namecheap

Get credentials from:

- <https://www.namecheap.com/support/api/intro/>

Required values:

- API key
- API username
- allowed client IP

Optional but important for purchasing:

- contact profile fields (name, address, phone, email).  
  Namecheap requires these for `namecheap.domains.create`.

## Behavior details

- Domain search uses cheap TLDs (`xyz`, `club`, `online`, `site`, `website`).
- Rotation is budget-gated (`monthly_budget` and `current_spending`).
- The manager can evaluate multiple configured registrars and select whichever
  returns an available domain within price limits.
- Domain ownership metadata includes registrar attribution.

## Security and safety

- Do not commit API keys.
- Start with a low monthly budget.
- Use registrar-side spending alerts where available.
- Treat Namecheap contact data as sensitive.

## References

- `docs/setup/DOMAIN_API_SETUP.md`
- `docs/user-guide/EMAIL_SYSTEM.md`
