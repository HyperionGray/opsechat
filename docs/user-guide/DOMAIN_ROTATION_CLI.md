# Domain Rotation CLI

## Overview

`domain_rotation_cli.py` manages burner-domain rotation through registrar APIs
(currently Porkbun). It also persists purchase/budget state in a local config
file so operators can resume where they left off between runs.

## Commands

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Configuration file

The CLI stores configuration at:

```text
~/.opsechat/domain_config.json
```

Stored keys:

- `api_key` / `api_secret`
- `monthly_budget`
- `current_spending`
- `active_domain`
- `owned_domains`

The file is written with mode `0600` to reduce accidental credential exposure.

## State persistence details

Owned domain records contain timestamps. The CLI serializes these fields as ISO
8601 strings when saving:

- `purchased_at`
- `expires_at`

When loading, the CLI:

1. Parses ISO timestamps (current format)
2. Falls back to legacy formats used by older configs
3. Leaves unknown values untouched instead of crashing

This prevents failures in `list`/`status` after upgrades and keeps backward
compatibility with existing operator state files.

## Typical workflow

1. Configure credentials and budget:
   ```bash
   python domain_rotation_cli.py config
   ```
2. Search for low-cost domains:
   ```bash
   python domain_rotation_cli.py search
   ```
3. Rotate (purchase + activate):
   ```bash
   python domain_rotation_cli.py rotate
   ```
4. Verify persisted state:
   ```bash
   python domain_rotation_cli.py list
   python domain_rotation_cli.py status
   ```

## Troubleshooting

- **`Error loading config`**: validate JSON in `~/.opsechat/domain_config.json`.
- **No domains listed after a successful run**: confirm `owned_domains` is in
  the config and includes `domain` + `price`.
- **Unexpected timestamp display**: legacy/invalid values are shown as-is; run
  one successful `rotate` to store normalized timestamps.
