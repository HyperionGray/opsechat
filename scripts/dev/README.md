Development Utility Scripts
===========================

This directory contains ad hoc developer helper scripts that were previously
kept in the repository root.

These scripts are not part of production runtime; they are convenience tools
for local validation, smoke tests, and troubleshooting.

Contents
--------

- `manual_release_validation.py` - interactive/manual release validation flow.
- `quick_import_test.py` - quick import sanity checks for core Python modules.
- `pf_task_smoke_test.py` - smoke test for `pf-tasks/` module imports.
- `mock_server_ci_check.js` - CI-oriented mock server startup/connectivity check.
- `mock_server_smoke.js` - lightweight mock server startup test.
- `run_targeted_runserver_helper_tests.sh` - targeted pytest helper script.
