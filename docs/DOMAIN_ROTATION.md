# Domain Rotation Guide

## Overview

OpSecChat includes a domain-rotation CLI that can:

- configure Porkbun API credentials,
- search for low-cost available domains,
- rotate (purchase and activate) a new domain,
- show current budget and active-domain status,
- list owned domains in local CLI state,
- prune expired domains from local CLI state.

The supported CLI is `domain_rotation_cli.py`.

## Supported Registrar

- Porkbun (`PorkbunAPIClient` in `domain_manager.py`)

Additional registrars can be added by implementing `DomainAPIClient`.

## Quick Start

```bash
# 1) Configure credentials and budget
python domain_rotation_cli.py config

# 2) Check current state
python domain_rotation_cli.py status

# 3) Search for cheap domains
python domain_rotation_cli.py search

# 4) Rotate to a newly found domain (prompts for confirmation)
python domain_rotation_cli.py rotate

# 5) List locally tracked owned domains
python domain_rotation_cli.py list

# 6) Remove expired domains from local state
python domain_rotation_cli.py prune
```

## CLI Commands

### `config`

Prompts for:

- Porkbun API key
- Porkbun API secret
- monthly budget (USD)

Writes config to:

- `~/.opsechat/domain_config.json`
- mode `0600` permissions

### `status`

Shows:

- active domain
- monthly budget
- current spending
- remaining budget
- owned domain count

### `search`

Runs a small search loop and prints low-cost candidate domains.

### `rotate`

Flow:

1. calculates remaining budget,
2. searches for an available low-cost domain,
3. asks for confirmation,
4. purchases domain via Porkbun API,
5. updates local state on success.

### `list`

Prints local owned-domain records with:

- domain name
- purchase price
- purchased timestamp
- expiration date
- active marker

### `prune`

Removes expired domain records from local CLI state and updates the active domain if needed.

## Data Persistence Model

The CLI persists local state in `~/.opsechat/domain_config.json`, including:

- API credentials,
- `current_spending`,
- `owned_domains`,
- `active_domain`.

Timestamps in `owned_domains` are serialized as ISO strings and parsed back to `datetime` on load.
This keeps `list`/`status` stable across restarts.

## Budget Controls

Built-in protections:

- purchase is denied when `current_spending + price > monthly_budget`,
- domain search is capped by `max_price`,
- status command surfaces remaining budget before rotation.

## Security Notes

- API credentials are sensitive; keep config file private.
- Do not commit credentials or copied config content to version control.
- Prefer dedicated registrar API keys with limited scope.

## Troubleshooting

### "API credentials not configured"

Run:

```bash
python domain_rotation_cli.py config
```

### "Could not find an available cheap domain within budget"

- increase budget,
- retry later (availability/pricing changes),
- confirm registrar API is reachable.

### "Budget exceeded"

- wait for your own budget policy reset,
- increase configured budget in `config`,
- prune expired local domains if state is stale:

```bash
python domain_rotation_cli.py prune
```
