# Email Configuration Workflow

## Overview

The email configuration page now provides a complete end-to-end workflow for:

- SMTP configuration
- IMAP configuration
- Domain rotation API configuration (Porkbun)
- Manual domain rotation
- IMAP fetch into the session inbox

This workflow is in-memory by design and does not persist credentials to disk.

## Implemented Behavior

### 1) SMTP and IMAP setup from `/email/config`

The form actions are now wired to active backend handlers in `email_routes.py`:

- `configure_smtp`
- `configure_imap`
- `configure_domain_api`

Each action:

1. Parses and validates submitted values.
2. Applies configuration to the active global manager.
3. Runs transport connection tests for SMTP/IMAP setup.
4. Stores a success/error status message in session for post-redirect rendering.

### 2) Domain manager web configuration

`DomainRotationManager` now exposes:

- `configure(api_key, secret_key, monthly_budget)`
- `get_config()`

These methods support UI-driven setup and status reporting without exposing raw secrets.

### 3) Domain rotation endpoint

`POST /<path>/email/domain/rotate` now exists in active routes and:

- attempts to rotate to a newly purchased domain based on current budget and API config,
- returns JSON for JSON clients,
- redirects with a status message for form submissions.

### 4) IMAP receive endpoint

`POST /<path>/email/receive` now exists in active routes and:

- fetches messages using configured IMAP transport,
- stores fetched emails in the current user inbox,
- returns JSON for JSON clients,
- redirects with fetched-count status for form submissions.

## CLI State Serialization Improvement

`domain_rotation_cli.py` now uses:

- `DomainRotationManager.export_state()`
- `DomainRotationManager.import_state()`

to safely serialize/deserialize `datetime` fields (`purchased_at`, `expires_at`) into JSON-compatible format.

This fixes state-save failures after successful domain purchases.

## Cleanup Performed

- Removed unused `email_security_routes.py` (stale, unregistered duplicate route implementation).

## Tests Added

- Extended `tests/test_domain_manager.py` to cover:
  - manager web configuration status
  - state export/import roundtrip
- Added `tests/test_email_config_routes.py` to verify:
  - config dashboard rendering
  - SMTP configuration action handling
  - domain API configuration action handling
  - domain rotation endpoint behavior
  - IMAP receive endpoint behavior
