## Domain Manager Runtime Updates

Date: 2026-03-18

### Summary

This update finishes previously partial domain-rotation runtime behavior and aligns active routes, CLI state handling, and domain manager APIs.

### What changed

1. Domain manager now supports runtime configuration and status export:
   - `configure(api_key, secret_key, monthly_budget, provider="porkbun")`
   - `get_config(mask_secrets=True)`

2. Added documented rotation/search APIs with structured results:
   - `search_cheap_domains(...)`
   - `rotate_to_new_domain(...)`
   - Existing `rotate_domain()` kept for compatibility (returns domain string).

3. Added compatibility helpers used by older scripts/docs:
   - `generate_random_domain_name(...)`
   - `generate_domain_name(...)`
   - `set_monthly_budget(...)`
   - `set_test_mode(...)`
   - `budget_manager` wrapper (`set_monthly_budget`, `get_month_spending`, `get_remaining_budget`)

4. State import/export is now JSON-safe:
   - `import_state(...)`
   - `export_state(...)`
   - Purchased/expires timestamps are persisted as ISO strings.

5. Email config route now uses active transport/domain managers and template-compatible variables:
   - SMTP/IMAP/domain config POST actions are handled.
   - Added `/email/receive` and `/email/domain/rotate` POST endpoints used by `templates/email_config.html`.

6. Domain CLI now loads/saves manager state via import/export and formats timestamp strings safely for display.

### Why this matters

- Prevents runtime failures caused by missing domain manager methods referenced by routes/docs.
- Prevents JSON serialization crashes when persisting purchased domain timestamps.
- Makes the shipped email configuration page functional with existing form actions.

### Test coverage

`tests/test_domain_manager.py` was expanded to cover:

- configuration + masked/unmasked config output,
- multi-domain search behavior,
- structured rotate result behavior,
- test-mode purchases without live API calls,
- import/export state round-trip behavior.
