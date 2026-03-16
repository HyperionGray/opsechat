# Domain Rotation CLI

This guide documents the `domain_rotation_cli.py` tool for managing burner-email
domain rotation with Porkbun.

## What is new

The CLI now persists domain state safely and supports automation-friendly
commands:

- Timestamp fields are serialized to JSON and restored on load.
- `rotate` supports non-interactive mode with `--yes`.
- `set-active <domain>` lets you switch the active domain without buying a new one.

## Configuration

```bash
python domain_rotation_cli.py config
```

Configuration is stored in:

```text
~/.opsechat/domain_config.json
```

File mode is set to `0600` on write.

## Commands

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py list
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py rotate --yes
python domain_rotation_cli.py set-active example.xyz
```

## State persistence behavior

`owned_domains` records include `purchased_at` and `expires_at`.
These fields are stored as ISO-8601 strings in JSON and converted back to
`datetime` objects at runtime.

This prevents failures in:

- `list` output formatting
- Saving manager state after rotation
- Reloading existing state from previous runs

## Notes for automation

Use `rotate --yes` for unattended workflows (cron/jobs). Budget checks still
apply and no purchase is attempted if budget is exhausted.

