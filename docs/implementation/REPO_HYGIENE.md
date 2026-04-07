# Repository Hygiene Automation

## Summary

This repository now includes an automated hygiene check to keep the tree organized and reduce stale artifacts.

Components added:

- `scripts/repo_hygiene.py` - Scanner and optional safe cleanup tool
- `.github/workflows/repo-hygiene.yml` - Scheduled and manual hygiene report workflow
- `Pfyfile.pf` task `hygiene` - Local report command

## What It Checks

The hygiene script scans for common low-value artifacts that often indicate unfinished or cluttered state:

- Backup/merge leftovers: `*~HEAD`, `*.orig`, `*.rej`
- Python cache artifacts: `__pycache__/`, `*.pyc`
- BISH artifacts: `.bish-index`, `.bish.sqlite`

By default it runs in report mode and does not modify files.

## Safe Cleanup Mode

To clean only known-safe items, use:

```bash
python scripts/repo_hygiene.py --fix-safe
```

Safe cleanup currently removes only:

- `*~HEAD`
- `*.orig`
- `*.rej`
- `__pycache__/`
- `*.pyc`

`--fix-safe` is intentionally conservative and does not remove `.bish-*` artifacts.

## Local Usage

Generate a hygiene report:

```bash
python scripts/repo_hygiene.py --report
```

or via pf:

```bash
pf Pfyfile.pf hygiene
```

## Scheduled Workflow

Workflow file: `.github/workflows/repo-hygiene.yml`

Trigger:

- Every 6 hours (`0 */6 * * *`)
- Manual via `workflow_dispatch`

Behavior:

- Checks out repository
- Runs hygiene report
- Appends report text to GitHub Actions job summary

## Notes

- The workflow is non-destructive.
- Cleanup remains explicit and local unless a future policy adds controlled automated fixes.
- The goal is to keep root and nested directories free of stale generated files while preserving intentional archives/history.
