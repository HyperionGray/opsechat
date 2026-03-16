# Domain Rotation Guide

This guide documents the currently supported domain-rotation workflow.

## Supported registrar

- Porkbun (via API key + secret key)

## CLI workflow

Configure API credentials:

```bash
python domain_rotation_cli.py config
```

Check status and owned domains:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

Search and rotate:

```bash
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
```

Manage local state:

```bash
python domain_rotation_cli.py activate example.xyz
python domain_rotation_cli.py prune-expired
python domain_rotation_cli.py reset-budget
```

## Budget behavior

- Purchases are blocked if they exceed the configured monthly budget.
- Spending automatically resets when the month changes (`YYYY-MM`, UTC).
- You can force a manual reset with `reset-budget`.

## State persistence

The CLI stores state in:

- `~/.opsechat/domain_config.json`

Persisted state includes:

- current spending
- owned domains
- active domain
- budget cycle marker

Datetime fields are serialized safely and restored on load.

## Related docs

- `docs/setup/DOMAIN_API_SETUP.md`
- `docs/setup/DOMAIN_REGISTRAR_API.md`
- `docs/implementation/DOMAIN_ROTATION_LIFECYCLE_UPDATE.md`
