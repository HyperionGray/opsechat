# Amazon Q Local Analyzer Heuristics

## Overview

When AWS-backed Amazon Q services are unavailable, OpSecChat now performs deterministic local analysis instead of returning placeholder values.

The local analyzers run in:

- `src/amazon_q/security_scanner.py`
- `src/amazon_q/quality_analyzer.py`
- `src/amazon_q/architecture_analyzer.py`

These analyzers keep the same high-level output schema used by the Amazon Q integration pipeline, so reports and downstream tooling continue to work.

## Security Scanner

`perform_security_scan()` now:

- scans analyzable source files across the repository (skips minified bundles),
- classifies findings by severity (`high`, `medium`, `low`),
- computes a bounded `risk_score` (0-100, where 100 is best).

Patterns include:

- hardcoded secrets,
- `subprocess(..., shell=True)` and `os.system(...)`,
- unsafe YAML loading,
- SQL injection-prone query construction,
- unsafe `innerHTML` assignment,
- `eval` / `exec`,
- unsafe pickle deserialization,
- weak hash usage (`md5`, `sha1`).

## Quality Analyzer

`analyze_code_quality()` now computes metrics from repository content:

- `maintainability_score`,
- `complexity_score`,
- `documentation_score`,
- `test_coverage_estimate`,
- and supporting context (`total_loc`, `function_count`, `avg_function_length`).

Issue detection includes:

- long functions,
- long lines,
- unfinished markers (`TODO`, `FIXME`, `TBD`, `XXX`),
- bare `except:`,
- missing Python module docstrings.

## Architecture Analyzer

`analyze_architecture()` now calculates a composite architecture score from:

- project structure quality,
- dependency health (including lockfile signal),
- design-pattern diversity.

Pattern detection includes common indicators for:

- singleton,
- factory,
- observer,
- strategy,
- decorator,
- repository.

## Notes

- Local analyzer outputs are heuristic, not formal proofs.
- The scoring model is deterministic and stable for CI trend tracking.
- AWS-backed analysis remains the preferred path when credentials and services are available.
