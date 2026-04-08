# Repository Hygiene Audit

## Overview

A lightweight repository hygiene audit is now part of automation to catch unfinished work and common cleanup issues early.

It checks:
- Unfinished markers in source/config files (`TODO`, `FIXME`, `STUB`, `TBD`, `XXX`, `WIP`, `HACK`, `UNFINISHED`)
- Stray backup/merge artifacts (for example `*~HEAD`, `*.orig`, `*.rej`)
- Unexpected empty files
- Nested duplicate directory patterns (for example `.github/.github`)

## Implementation

- Script: `scripts/repo_hygiene_audit.py`
- Workflow: `.github/workflows/repository-hygiene-audit.yml`
- Schedule: every 3 hours + manual (`workflow_dispatch`)

The workflow:
1. Checks out the repository
2. Runs the hygiene audit script
3. Uploads markdown + JSON artifacts
4. Creates or updates a single issue (`Repository Hygiene Audit Findings`) when findings exist
5. Closes the issue automatically when findings return to zero

## Manual Usage

Run from repository root:

```bash
python3 scripts/repo_hygiene_audit.py --root .
```

Write artifacts:

```bash
python3 scripts/repo_hygiene_audit.py \
  --root . \
  --report-path .tmp/hygiene/report.md \
  --summary-path .tmp/hygiene/summary.json
```

Include docs/TODO markdown in marker scans:

```bash
python3 scripts/repo_hygiene_audit.py --root . --scan-docs
```

Fail CI when findings are present:

```bash
python3 scripts/repo_hygiene_audit.py --root . --fail-on-findings
```

## Notes

- By default, marker scanning focuses on source/config files and skips `docs/` + top-level TODO docs to reduce noise.
- The script intentionally ignores archived content in `bak/`.
- This audit is a hygiene signal; it does not replace security scanning or test execution.
