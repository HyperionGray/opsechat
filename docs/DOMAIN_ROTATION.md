# Domain Rotation Guide

This document was previously out of sync with the implementation and referenced
methods that no longer exist.

For current, tested registrar and rotation behavior, use:

- `docs/setup/DOMAIN_REGISTRAR_API.md` (registrar support and CLI workflow)
- `docs/setup/DOMAIN_API_SETUP.md` (operational setup details)

Current implementation entry points:

- `domain_manager.py`
  - `PorkbunAPIClient`
  - `NamecheapAPIClient`
  - `DomainRotationManager`
- `domain_rotation_cli.py`
  - `config`, `status`, `search`, `rotate`, `list`

Quick commands:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```
