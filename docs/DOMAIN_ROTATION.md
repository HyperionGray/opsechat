# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. The
current implementation supports multiple registrar providers with primary-first
fallback behavior.

## Supported Registrars

- Porkbun
- Namecheap

Both are configurable through `domain_rotation_cli.py`. Domain search and
purchase can be restricted to one provider or run with fallback across all
configured providers.

## CLI Usage

### Configure registrar credentials

```bash
# Configure Porkbun
python domain_rotation_cli.py config --registrar porkbun

# Configure Namecheap
python domain_rotation_cli.py config --registrar namecheap
```

During configuration, you can set:
- registrar credentials
- default registrar
- monthly budget

### Check status and domains

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py list
```

Status output now includes configured providers and the current primary provider.

### Search and rotate

```bash
# Search using all configured providers (primary first)
python domain_rotation_cli.py search

# Search using only one provider
python domain_rotation_cli.py search --provider namecheap

# Rotate using all configured providers
python domain_rotation_cli.py rotate

# Rotate using a specific provider
python domain_rotation_cli.py rotate --provider porkbun
```

## Fallback Behavior

When no `--provider` is supplied:

1. The primary provider is tried first.
2. Remaining configured providers are tried in order.
3. The first available, in-budget domain is selected.

This improves reliability when one registrar has temporary API issues or poor
availability for random candidates.

## Namecheap Notes

Namecheap purchases require a contact profile. The CLI collects this in
`config --registrar namecheap`.

Search operations can still work with partial Namecheap configuration, but
purchase will fail with an explicit missing-fields message until the profile is
complete.

## State Persistence

The manager now persists domain state in a JSON-safe format and restores it
on startup:
- `purchased_at` / `expires_at` are serialized as ISO timestamps
- timestamps are parsed back into datetimes when loading

This keeps `list` and `status` stable across runs.

## Security and Cost Recommendations

- Use low monthly budgets for initial rollout.
- Prefer low-cost TLDs (`.xyz`, `.club`, `.online`) for burner use.
- Keep registrar API credentials out of version control.
- Enable registrar-side security controls (2FA, API key rotation).
