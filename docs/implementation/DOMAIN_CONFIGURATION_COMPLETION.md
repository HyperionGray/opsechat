# Domain Configuration Completion

## Summary

This update completes and hardens the domain configuration workflow across the web UI and CLI tooling.

The main goal was to finish previously incomplete integration points and remove stale repository artifacts.

## What Was Completed

### 1) Domain manager configuration API completed

`domain_manager.py` now includes:

- `DomainRotationManager.configure(api_key, secret_key, monthly_budget)`
- `DomainRotationManager.get_config()`

These methods are now used by the email configuration route and expose a safe, in-memory configuration summary suitable for UI rendering.

### 2) Domain state import/export added for CLI persistence

`DomainRotationManager` now supports:

- `export_state()` for JSON-safe serialization
- `import_state()` for robust restoration of runtime state

The implementation normalizes:

- price values (`$2.99`, numeric, etc.)
- datetime fields (`datetime` objects and ISO 8601 strings)

This resolves serialization issues when saving purchased-domain state through `domain_rotation_cli.py`.

### 3) Email configuration flow fixed end-to-end

`email_routes.py` was updated so `/email/config` now:

- handles the actual form `action` values emitted by `templates/email_config.html`
- configures SMTP/IMAP through `transport_manager`
- configures domain API through `domain_rotation_manager`
- returns clear success/error feedback via redirect-safe session messaging

Also added:

- `POST /<path>/email/domain/rotate`

This route rotates the active domain and reports result status back to the configuration page.

### 4) Tests added/expanded

- `tests/test_domain_manager.py`
  - new coverage for config methods
  - state export/import round-trip coverage

- `tests/test_email_routes.py` (new)
  - GET config page rendering
  - POST configure-domain flow
  - POST configure-SMTP flow
  - POST domain-rotate flow

Focused test run result:

- `17 passed`

## Repository Cleanup Performed

Removed tracked stale artifacts:

- backup files: `Dockerfile~HEAD`, `docker-compose.yml~HEAD`
- accidental build/index artifacts: multiple tracked `.bish-index` files across root and subdirectories

Also cleaned a stale doc marker:

- `docs/README.md` quick-start line no longer marked as TODO

## Why This Matters

This change completes the domain-management direction already present in recent work:

- container/release preparation
- operational deployment docs
- burner-email domain rotation support

The project now has a functional, test-backed domain configuration path through both:

- Web UI (`/email/config`)
- CLI (`domain_rotation_cli.py`)
