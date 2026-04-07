# Repository Hygiene Automation

This repository now includes an automated hygiene checker for scheduled maintenance runs.

## What it checks

`scripts/check_repo_hygiene.py` scans tracked files (`git ls-files`) and reports:

1. **Unfinished markers in source comments**
   - Markers: `TODO`, `FIXME`, `STUB`, `TBD`, `HACK`, `XXX`
   - File types: `.py`, `.js`, `.ts`, `.tsx`, `.sh`
   - Scope excludes `docs/` and `bak/` for marker checks so planning notes do not fail the check
2. **Stale tracked artifacts**
   - Backup suffixes such as `~HEAD`, `.orig`, `.rej`, `.bak`, `.tmp`
   - Known stray basenames: `.DS_Store`, `Thumbs.db`, `.bish-index`, `.bish.sqlite`, `test-ci-fix.js`, `test-server.js`
3. **Redundant directory nesting**
   - Immediate repeated directory segments like `src/src/file.py`

## Usage

Run directly:

```bash
python3 scripts/check_repo_hygiene.py --strict
```

Machine-readable output:

```bash
python3 scripts/check_repo_hygiene.py --strict --json
```

Run through PF task:

```bash
pf Pfyfile.pf hygiene
```

## Integration

- Added PF task:
  - `task hygiene python3 scripts/check_repo_hygiene.py --strict`
- Added to test flow:
  - `pf-tasks/test.py` now runs hygiene checks in `--method all` mode.
- Added tests:
  - `tests/test_repo_hygiene.py`

## Why this exists

Scheduled automation is expected to continuously clean up unfinished/stale repository state. This check turns that expectation into an executable rule so regressions are detected early and consistently.
