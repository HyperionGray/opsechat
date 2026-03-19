# Amazon Q Local Analyzer Upgrade (2026-03)

## Summary

This update replaces demo-limited analyzer behavior in `src/amazon_q/` with full local heuristic analysis across the repository.

## What Changed

### 1) Source file discovery is now configurable and cleaner
- Updated `src/amazon_q/utils.py`:
  - Added configurable extension/exclude/max-file filters in `get_source_files(...)`.
  - Added default exclusion for generated/vendor artifacts (for example `*.min.js`).
  - Added deterministic sorting of discovered files.

### 2) Code quality analyzer now computes real metrics
- Updated `src/amazon_q/quality_analyzer.py`:
  - Replaced fixed placeholder scores with dynamic metrics derived from findings.
  - Added Python AST-based checks for:
    - long functions,
    - missing module/function docstrings,
    - high complexity functions.
  - Added generic checks for non-Python files (long blocks and complexity signal).
  - Added optional custom-rule checks for TODO/FIXME and debug statements.
  - Maintains existing output schema: `metrics`, `issues`, `total_files_analyzed`, timestamp/analyzer metadata.

### 3) Security scanner now scans all discovered source files
- Updated `src/amazon_q/security_scanner.py`:
  - Removed demo cap that only scanned the first subset of files.
  - Added richer issue signatures (hardcoded secrets/passwords, SQL injection patterns, shell injection, dynamic eval/exec, DOM XSS sinks).
  - Added per-severity counters in results while preserving existing fields.

### 4) Architecture analysis scoring is now derived from findings
- Updated `src/amazon_q/architecture_analyzer.py`:
  - Removed hardcoded architecture score.
  - Computes score from project structure, pattern analysis, and dependency profile.
  - Pattern scan now processes all discovered source files and includes adapter/facade indicators.

## Test Coverage Added

Added `tests/test_amazon_q_analyzers.py` with focused checks for:
- full-file security scan coverage (not demo-limited),
- dynamic quality metrics with custom TODO detection,
- architecture pattern detection beyond the old first-N-file behavior,
- source file discovery exclusion of minified assets.

## Repository Cleanup Included

- Removed stale duplicate entry points:
  - `runserver_refactored.py`
  - `tests/mock_server_refactored.py`
- Updated `docs/development/DEVELOPMENT.md` to remove obsolete `runserver_refactored.py` reference.
