# Domain Rotation CLI (`rotate-domain.py`)

This document covers the simplified domain operations CLI for operators.

## Purpose

`rotate-domain.py` is a concise wrapper around domain APIs for common tasks:

- Search one domain for availability and price
- Buy one domain with explicit confirmation
- List currently owned domains
- Query pricing for one TLD

It is intended for non-programmer operators who want simple commands.

## Credentials

Credentials are loaded in this order:

1. CLI flags: `--api-key`, `--api-secret`
2. Environment variables: `PORKBUN_API_KEY`, `PORKBUN_API_SECRET`
3. `~/.opsechat/domain_config.json` (created by `domain_rotation_cli.py config`)

## Usage

### Search a domain

```bash
python3 rotate-domain.py --search example.xyz
```

### Buy a domain

```bash
# Interactive confirmation
python3 rotate-domain.py --buy example.xyz --years 1

# Non-interactive (automation)
python3 rotate-domain.py --buy example.xyz --years 1 --yes
```

### List owned domains

```bash
python3 rotate-domain.py --list-owned
```

### Get TLD pricing

```bash
python3 rotate-domain.py --get-pricing xyz
```

### Interactive mode

```bash
python3 rotate-domain.py --interactive
```

## Budget behavior

The CLI enforces budget checks for `--buy` when a budget is configured.

- Uses configured `monthly_budget` and `current_spending` from `~/.opsechat/domain_config.json`
- Optional override for one command: `--budget 25.00`
- Blocks purchases that would exceed budget

On successful purchase, `current_spending` is updated in the config file.

## Exit codes

- `0`: success
- `1`: failure (for example: unavailable domain, missing credentials, budget block, API error)
