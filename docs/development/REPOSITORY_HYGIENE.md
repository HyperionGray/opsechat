# Repository Hygiene Guide

This project now includes a repository hygiene audit task to keep cleanup work continuous and visible.

## What the Audit Checks

`pf-tasks/audit.py` reports:

- unfinished markers in tracked text files (`TODO`, `FIXME`, `STUB`, `TBD`, `UNFINISHED`, `WIP`, `XXX`, `HACK`)
- stale naming patterns (`*.bak`, `*.old`, `*.orig`, `*.tmp`, `*.deprecated`)
- repeated nested directory segments (for example `foo/foo/...`)
- deep directory structures beyond a configurable depth
- empty directories that are often stale leftovers

The audit is read-only and does not modify files.

## Usage

```bash
# Human-readable output
python pf-tasks/audit.py

# JSON output for automation pipelines
python pf-tasks/audit.py --format json

# Fail with exit code 1 if findings exist
python pf-tasks/audit.py --fail-on-findings

# Customize depth and output volume
python pf-tasks/audit.py --max-depth 3 --limit 25
```

## Interpreting Results

- Treat findings as prompts for review, not automatic deletion instructions.
- Documentation files may legitimately contain roadmap markers; prioritize source/runtime code first.
- For stale candidates, confirm references before deletion.
- For deep path findings, consider flattening only when it improves maintainability and clarity.

## Suggested Maintenance Loop

1. Run `python pf-tasks/audit.py`.
2. Fix or remove confirmed stale items.
3. Re-run with `--fail-on-findings` to validate progress.
4. Keep intentional roadmap notes consolidated in dedicated planning docs (`TODO.md`, `TODO-automation.md`).
