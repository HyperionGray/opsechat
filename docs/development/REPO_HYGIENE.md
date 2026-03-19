# Repository Hygiene Checks

This repository includes an automated hygiene checker to keep the tree clean
and prevent unfinished or stale implementation artifacts from drifting into
mainline development.

## Script

- `scripts/repo_hygiene.py`

## What It Checks

1. Unfinished markers in source code (`TODO`, `FIXME`, `HACK`, `XXX`)
2. Tracked `.bish-index` artifacts
3. Unexpected nested workflow placeholders under `.github/.github/workflows`
4. Stale `_refactored.py` duplicates when a canonical `.py` file also exists

## Local Usage

Run checks:

```bash
python scripts/repo_hygiene.py
```

Run checks and auto-fix safe artifacts:

```bash
python scripts/repo_hygiene.py --fix
```

JSON output:

```bash
python scripts/repo_hygiene.py --json
```

## CI Integration

The `Repository Hygiene` job in `.github/workflows/ci.yml` runs this check on
push and pull request events to stop regressions early.
