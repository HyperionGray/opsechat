# Domain Rotation

This document provides a quick reference for burner-domain rotation in opsechat.
For full registrar setup and operational detail, use:

- `docs/setup/DOMAIN_REGISTRAR_API.md`

## CLI Commands

```bash
# Configure registrar credentials and budget
python domain_rotation_cli.py config

# Search candidates under a price ceiling
python domain_rotation_cli.py search --max-price 3 --attempts 8

# Rotate to a new domain (non-interactive mode for automation)
python domain_rotation_cli.py rotate --max-price 4 --yes

# Show budget/expiry report
python domain_rotation_cli.py report

# Remove expired domains from local CLI state
python domain_rotation_cli.py prune
```

## Notes

- Local CLI state is stored in `~/.opsechat/domain_config.json`
- State persistence is JSON-safe (datetimes serialized as ISO-8601 strings)
- File permissions are written as `0600`
