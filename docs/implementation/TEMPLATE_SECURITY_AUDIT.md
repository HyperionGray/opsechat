# Template Security Audit

## Summary

OpSecChat now performs a startup audit of template files to detect inline script/style
constructs that conflict with the strict CSP headers set in `app_factory.py`.

This closes the previously open checklist item about verifying template compatibility
with CSP restrictions.

## What is checked

The audit scans templates for:

- Inline `<script>` tags without `src=`
- Inline `<style>` tags
- Inline `style=` attributes
- Inline event handlers such as `onclick=`, `onload=`, etc.

## Configuration

Use environment variables to control behavior:

```bash
# Default: scan and log findings
TEMPLATE_AUDIT_MODE=warn

# Enforce as startup gate (raises RuntimeError if findings exist)
TEMPLATE_AUDIT_MODE=strict

# Disable audit
TEMPLATE_AUDIT_MODE=off

# Optional: comma-separated files relative to templates/
TEMPLATE_AUDIT_EXCLUDE_FILES=legacy.html,old/layout.html
```

## Files

- `template_security_audit.py` - Scanner/enforcement utilities
- `app_factory.py` - Startup wiring for audit mode and excludes
- `tests/test_template_security_audit.py` - Unit tests for scanner and enforcement
- `tests/test_security_headers.py` - Integration checks for strict/off behavior

## Notes

- `warn` mode is suitable while migrating legacy templates.
- `strict` mode is recommended once all legacy inline markup is removed.
