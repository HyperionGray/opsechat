# Repository Hygiene Automation

This project now includes an automated repository hygiene audit to detect stale files and unfinished repository artifacts early.

## What it checks

The audit script is `scripts/repo_hygiene_audit.py` and currently scans for:

- backup artifacts committed by mistake (`*~HEAD`, `*.orig`, `*.rej`)
- accidental nested `.github/.github` directories
- placeholder workflow files (`# Placeholder workflow for ...`)
- GitHub workflow references to missing Python scripts
- empty suspicious files (except `.gitkeep` / `.keep`)

## Run locally

```bash
python3 scripts/repo_hygiene_audit.py --root .
python3 scripts/repo_hygiene_audit.py --root . --json --fail-on-findings
```

## CI workflow

The workflow `.github/workflows/repo-hygiene-audit.yml` runs:

- on manual dispatch
- twice daily by cron

It fails when findings are detected and uploads `repo-hygiene-report.txt` as an artifact.

## Related automation fix

The existing workflow `.github/workflows/trigger-all-repos.yml` now uses
`scripts/trigger_workflow_all_repos.py` so its referenced dispatch script is actually present in the repository.
