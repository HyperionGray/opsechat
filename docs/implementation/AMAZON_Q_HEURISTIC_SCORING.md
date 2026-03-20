# Amazon Q Heuristic Scoring

## Summary

The Amazon Q integration now computes architecture and quality scores from repository data instead of fixed placeholder values.

Updated modules:

- `src/amazon_q/architecture_analyzer.py`
- `src/amazon_q/quality_analyzer.py`

## What changed

### Architecture scoring

`analyze_architecture()` now derives `architecture_score` from three sub-scores:

- Structure score (45%):
  - README, license, `.gitignore`, and dependency manifest presence
  - file-type diversity
  - basic repository size signal
- Dependency hygiene score (25%):
  - dependency count bands
  - lockfile presence when dependencies exist
- Design score (30%):
  - heuristic design-pattern detection

All scores are clamped to `0-100`.

### Quality scoring

`analyze_code_quality()` now computes metrics from observed issues and file makeup:

- `maintainability_score`: decreases as issue density increases
- `complexity_score`: decreases with detected long functions
- `documentation_score`: decreases with missing Python module docstrings
- `test_coverage_estimate`: estimated from detected test-file to non-test-file ratio

The analyzer now processes up to 50 source files per run and reports:

- `total_files_analyzed`
- `total_files_discovered`

### Long-function detection fix

`analyze_file_quality()` now also flags long functions that reach end-of-file.
Previously this case could be missed if no subsequent function declaration appeared.

## Validation

Added pytest coverage in `tests/test_amazon_q_analyzers.py` to verify:

1. architecture scoring favors better-structured repositories,
2. long function detection works at end-of-file,
3. quality metrics improve for cleaner code with tests.
