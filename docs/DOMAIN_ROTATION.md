# Domain Rotation Guide

This document is kept as a compatibility entry point for older references.

For current setup and operational guidance, use:

- [Domain API Setup](setup/DOMAIN_API_SETUP.md)
- [Domain Registrar API](setup/DOMAIN_REGISTRAR_API.md)

## CLI Quick Reference

The supported domain rotation CLI commands are:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## State Storage

The CLI stores local state in:

`~/.opsechat/domain_config.json`

Stored fields include API credentials, monthly budget, spending totals, active
domain, and owned-domain history. Datetime fields are serialized as ISO-8601
strings and restored when loaded.
