# Domain Rotation Guide

## Overview

OpSecChat includes a domain rotation manager for burner email workflows. The current implementation supports Porkbun and focuses on:

- finding low-cost available domains
- enforcing a monthly spend budget
- purchasing and tracking owned domains
- persisting manager state in a local CLI config file
- pruning expired domains from tracked state

## CLI Commands

The domain CLI entrypoint is:

```bash
python domain_rotation_cli.py <command>
```

Available commands:

- `config` - configure API credentials and monthly budget
- `status` - show active domain and budget status
- `search` - search for cheap available domains
- `rotate` - find and purchase a new active domain
- `list` - list owned domains in local saved state
- `prune` - remove expired domains from local saved state

## Setup

### 1) Create Porkbun API keys

1. Sign in to https://porkbun.com
2. Open Account -> API Access
3. Create and copy:
   - API Key
   - Secret API Key

### 2) Configure OpSecChat domain CLI

Run:

```bash
python domain_rotation_cli.py config
```

The command stores configuration in:

```text
~/.opsechat/domain_config.json
```

File permissions are set to `0600`.

## State Persistence

The manager now serializes domain state safely for JSON storage.

Saved fields:

- `current_spending`
- `active_domain`
- `owned_domains`

For `owned_domains`, `purchased_at` and `expires_at` are stored as ISO-8601 strings and converted back to `datetime` values when loading.

This avoids prior failures when writing Python `datetime` objects directly to JSON.

## Typical Workflow

### Search for candidate domains

```bash
python domain_rotation_cli.py search
```

### Purchase and activate a domain

```bash
python domain_rotation_cli.py rotate
```

### View local state

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

### Prune expired tracked domains

```bash
python domain_rotation_cli.py prune
```

If the active domain has expired and is pruned, the manager will select the most recently tracked remaining domain as the new active domain (or `None` if none remain).

## Budget Controls

Budget guardrails are enforced before purchase:

- if `current_spending + price > monthly_budget`, purchase is denied
- default monthly budget is `$50.00`

Use `status` to inspect:

- monthly budget
- current spending
- remaining budget
- tracked domain count

## Troubleshooting

### "API credentials not configured"

Run:

```bash
python domain_rotation_cli.py config
```

### "Could not find available cheap domain"

Possible reasons:

- random candidate domains were unavailable
- registrar/API issue
- returned price could not be parsed

Retry search or rotate after a short delay.

### Purchase denied due to budget

Increase monthly budget via `config` or wait until your accounting period resets in your operational workflow.

## Extending to More Registrars

Additional registrars can be added by implementing `DomainAPIClient`:

- `search_domain(domain)`
- `purchase_domain(domain, years=1)`
- `get_pricing(tld)`

Then provide that client to `DomainRotationManager`.
