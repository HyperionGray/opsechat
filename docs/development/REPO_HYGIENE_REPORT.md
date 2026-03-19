# Repository Hygiene Report Automation

## Overview

`scripts/repo_hygiene_report.py` generates a markdown report used by scheduled automation runs.

The report summarizes:

- Unfinished markers in code files (`TODO`, `FIXME`, `STUB`, `TBD`, `XXX`, `UNFINISHED`)
- Python function stubs with pass-only or ellipsis-only bodies
- Cleanup candidates (duplicate `_refactored.py` patterns and loose root-level test helpers)
- Recent project direction inferred from recent commit messages

## Usage

Run from repository root:

```bash
python3 scripts/repo_hygiene_report.py --repo-root . --commits 12 --max-items 30
```

Write report to a file:

```bash
python3 scripts/repo_hygiene_report.py \
  --repo-root . \
  --commits 12 \
  --max-items 30 \
  --output /tmp/repo-hygiene.md
```

Fail the command when unfinished code is detected:

```bash
python3 scripts/repo_hygiene_report.py --repo-root . --fail-on-unfinished
```

## Workflow Integration

The workflow `.github/workflows/daily-continuous-progress.yml` now:

1. Generates `/tmp/repo-hygiene.md` using this script
2. Creates or updates the daily progress issue using the generated report

This replaces a static issue template with a concrete repo-state snapshot.
