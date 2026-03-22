# Domain Rotation CLI State and Cleanup

This document covers the local state behavior of `domain_rotation_cli.py`.

## Overview

The domain rotation CLI stores state in:

`~/.opsechat/domain_config.json`

State now includes:

- `current_spending`
- `active_domain`
- `owned_domains` (with ISO-8601 timestamps)

This allows `list`, `status`, and `rotate` to survive CLI restarts.

## Datetime persistence

`owned_domains` timestamps are serialized as ISO-8601 strings:

```json
{
  "domain": "abc123xy.xyz",
  "price": 2.99,
  "purchased_at": "2026-03-22T20:30:10.123456",
  "expires_at": "2027-03-22T20:30:10.123456"
}
```

On load, the CLI parses these values back into datetimes for runtime use.

## Cleanup command

Use the new cleanup command to prune expired domains from local state:

```bash
python domain_rotation_cli.py cleanup
```

What it does:

1. Removes domains whose `expires_at` is in the past
2. Reassigns `active_domain` if the current active domain expired
3. Saves the cleaned state back to `~/.opsechat/domain_config.json`

## Recommended maintenance

- Run `cleanup` periodically (for example, via cron).
- Run `status` after cleanup to confirm active domain and budget values.
