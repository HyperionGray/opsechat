# Amazon Q Local Analyzer Enhancements (2026-03-30)

## Summary

The `src/amazon_q` analyzer modules were upgraded from demo-limited placeholder behavior to deterministic, full-repository local analysis.

This work makes mock/local Amazon Q reviews useful in CI and development environments even when AWS services are unavailable.

## What changed

### 1) Security scanner (`src/amazon_q/security_scanner.py`)

- Removed first-N-file demo limit and now scans all source files discovered by `get_source_files`.
- Replaced placeholder pattern list with explicit rule definitions and severities:
  - hardcoded secrets
  - SQL injection patterns
  - `innerHTML` DOM writes
  - `subprocess(..., shell=True)`
  - `os.system(...)`
  - `eval(...)`
  - `pickle.load/loads(...)`
- Added deterministic UTC timestamps using timezone-aware `datetime`.
- Added `severity_summary` and analyzer metadata (`codewhisperer_configured`).

### 2) Quality analyzer (`src/amazon_q/quality_analyzer.py`)

- Removed demo file limits.
- Added configurable thresholds via `custom_rules`:
  - `long_function_lines`
  - `max_line_length`
  - `complexity_threshold`
- Added richer issue detection:
  - long functions
  - high branch complexity
  - unfinished markers (`TODO`, `FIXME`, `XXX`, `TBD`)
  - bare `except:`
  - missing Python module docstrings
  - overlong lines
- Added deterministic metric calculation:
  - `maintainability_score`
  - `complexity_score`
  - `documentation_score`
  - `test_coverage_estimate` (heuristic)
- Added `severity_summary`, skipped test-file count, and analyzer metadata (`bedrock_configured`).

### 3) Architecture analyzer (`src/amazon_q/architecture_analyzer.py`)

- Replaced static architecture score with computed score derived from:
  - structure analysis
  - dependency health
  - design-pattern score
  - anti-pattern penalties
- Improved structure analysis:
  - ignored cache/vendor directories
  - tracks top-level directories
  - checks presence of `VERSION`
  - reports missing expected core directories (`src`, `tests`, `docs`, `templates`, `static`)
- Improved dependency analysis:
  - includes dependency count and lockfile health
  - computes `dependency_health_score`
- Improved design/anti-pattern analysis:
  - scans all source files (no demo limit)
  - adds `dataclass` pattern detection
  - detects anti-patterns like runtime `sys.path.insert(...)`

### 4) Mock reviewer parity (`src/amazon_q/mock_reviewer.py`)

- Mock mode now uses the same local security/quality/architecture analyzers rather than fixed dummy values.
- This keeps `mock_review()` realistic and deterministic while preserving `mock_mode=True` semantics.

### 5) Timestamp consistency

- Updated reviewer and mock reviewer timestamps to timezone-aware UTC format.

## Tests added

New test file:

- `tests/test_amazon_q_analyzers.py`

Coverage includes:

- high-risk security pattern detection
- quality issue and metrics generation
- architecture pattern + anti-pattern detection
- mock reviewer integration using real local analyzers

## Why this direction

Recent repository activity focused on CI/workflow and stabilization. Improving analyzer quality increases the usefulness of automated review outputs without adding runtime dependencies or external service requirements.
