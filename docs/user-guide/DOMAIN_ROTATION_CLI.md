# Domain Rotation CLI

This repository includes two command-line interfaces for domain operations:

- `domain_rotation_cli.py`: interactive setup and guided workflows
- `rotate-domain.py`: non-interactive command mode for automation/scripts

## Prerequisites

1. Porkbun API credentials
2. Python dependencies installed (`pip install -r requirements.txt`)

You can provide credentials in any of these ways:

- Command flags: `--api-key`, `--api-secret`
- Environment variables:
  - `PORKBUN_API_KEY`
  - `PORKBUN_API_SECRET`
- Config file: `~/.opsechat/domain_config.json`

## Usage

### Search domain availability

```bash
python rotate-domain.py --search example.xyz
```

### Purchase a domain

```bash
python rotate-domain.py --buy example.xyz --years 1 --confirm
```

`--confirm` is required to reduce accidental purchases.

### List owned domains

```bash
python rotate-domain.py --list-owned
```

### Get TLD pricing

```bash
python rotate-domain.py --get-pricing xyz
```

## Output

`rotate-domain.py` prints JSON to stdout so it can be piped to other tools.

## Notes

- The interactive `domain_rotation_cli.py` now persists owned domain timestamps safely.
- Stored domain timestamps are serialized as ISO 8601 and restored automatically.
