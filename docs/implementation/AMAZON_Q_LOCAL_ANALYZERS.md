# Amazon Q Local Analyzer Enhancements

## Summary

The local Amazon Q fallback analyzers now perform real heuristic analysis instead of returning fixed placeholder values.

Updated modules:

- `src/amazon_q/security_scanner.py`
- `src/amazon_q/quality_analyzer.py`
- `src/amazon_q/architecture_analyzer.py`

## What Changed

### 1. Security Scanner Improvements

- Scans all analyzable source files (excluding minified/generated/vendor paths).
- Detects common risky patterns:
  - hardcoded secrets,
  - shell execution with `shell=True`,
  - dynamic execution (`eval`/`exec`),
  - suspicious SQL string interpolation,
  - potential DOM XSS sinks (`innerHTML`),
  - weak hash usage (`md5`/`sha1`).
- Adds severity summary and repository-level `risk_score` (0-100).

### 2. Code Quality Analyzer Improvements

- Computes quality metrics from repository content:
  - `maintainability_score`,
  - `complexity_score`,
  - `documentation_score`,
  - `test_coverage_estimate`.
- Uses language-aware checks:
  - Python AST parsing for function length/complexity/docstrings,
  - JS/TS heuristic function span and branching checks.
- Reports additional issue types such as:
  - `large_file`,
  - `long_function`,
  - `high_complexity`,
  - `missing_docstring`,
  - `missing_function_docstring`,
  - `technical_debt_marker`.

### 3. Architecture Analyzer Improvements

- Structure analysis now evaluates:
  - common repository directories,
  - directory depth,
  - repeated nested directory names.
- Dependency analysis now includes:
  - pinned vs unpinned Python dependencies,
  - lockfile awareness,
  - computed `dependency_score`.
- Pattern analysis now scans analyzable source files for practical pattern indicators.
- Final `architecture_score` is now computed from structure/dependency/pattern sub-scores.

## Test Coverage Added

New tests in `tests/test_amazon_q_analyzers.py` verify:

- security issue detection and severity/risk output,
- quality issue detection and non-placeholder metrics,
- architecture scoring and dependency/pattern analysis behavior.

## Notes

- The analyzers remain local heuristics and are designed as robust fallback logic when full managed service integration is unavailable.
- Return schemas remain compatible with existing review/reporting callers.
