# Daily Progress Automation

This document describes how the daily progress workflow gathers context and creates actionable issues for automated coding agents.

## Workflow

The workflow file is:

- `.github/workflows/daily-continuous-progress.yml`

On each run (scheduled or manual), it now:

1. Checks out a short recent history (`fetch-depth: 30`)
2. Runs `scripts/repo_direction_analyzer.py`
3. Saves a markdown summary to `/tmp/repo-direction.md`
4. Creates the daily progress issue and includes that summary in the issue body
5. Mentions `@copilot` and includes the same summary in the trigger comment

## Repository Direction Analyzer

The analyzer script:

- Reads the most recent commits (default 8)
- Aggregates changed files by top-level area (`.github`, `tests`, `docs`, etc.)
- Produces "Suggested next steps" based on current activity
- Flags simple hygiene issues (for example, nested `.github/.github` paths)

Run locally:

```bash
python scripts/repo_direction_analyzer.py --limit 8
```

## Why this helps

Instead of creating generic daily tasks, the workflow now provides a commit-driven snapshot of current development direction. This improves automation quality by grounding agent prompts in recent repository activity and hygiene signals.
