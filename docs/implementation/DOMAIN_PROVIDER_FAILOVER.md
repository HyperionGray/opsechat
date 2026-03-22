# Domain Provider Failover (Porkbun + Namecheap)

## What was added

`domain_manager.py` now supports multiple registrar clients in the same
`DomainRotationManager` instance:

- Porkbun client (existing)
- Namecheap client (new)
- Provider-aware selection and purchase metadata
- Automatic fallback search across configured providers

The manager now exposes:

- `add_api_client(provider, client, make_primary=False)`
- `set_primary_api_client(provider)`
- `configure(...)`
- `get_config()`

## Why this matters

Domain rotation previously depended on one registrar path. If that provider had
availability gaps, API issues, or pricing mismatches, rotation could fail even
when another provider had viable domains.

Failover search now improves resilience by trying providers in priority order.

## Implementation notes

- `DomainRotationManager.find_cheap_available_domain()` now iterates providers,
  parses different price formats, and returns provider metadata.
- `purchase_domain_if_budget_allows()` accepts an optional `provider` argument,
  and records provider origin in owned-domain metadata.
- Added `NamecheapAPIClient` with:
  - domain availability checks
  - pricing query support
  - purchase flow using Namecheap contact payload requirements

## Email security route fixes

`email_security_routes.py` integration gaps were fixed to align with real
transport/domain manager APIs:

- fixed SMTP/IMAP parameter wiring
- added non-secret transport config read API (`EmailTransportManager.get_config`)
- fixed domain rotation API JSON response shape

## CLI reliability fix

`domain_rotation_cli.py` now serializes/deserializes domain ownership timestamps
as ISO strings, preventing JSON save/load failures when state is persisted.

## Tests

Extended `tests/test_domain_manager.py` coverage includes:

- price parsing variants
- provider failover behavior
- provider-specific purchase path
- Namecheap XML parsing behavior
- Namecheap purchase contact validation
