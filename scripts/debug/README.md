Debug utility scripts
=====================

This directory contains ad-hoc troubleshooting scripts that are useful for
local diagnostics but are not part of the main production/test pipeline.

Current scripts:
- `mock-server-smoke.js`: quick local mock-server startup check
- `ci-mock-server-check.js`: CI-focused mock-server connectivity probe
- `targeted-pytest-check.sh`: runs a targeted pytest subset
