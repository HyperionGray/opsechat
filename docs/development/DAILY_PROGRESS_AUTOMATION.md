# Daily Progress Automation

## Purpose

`/.github/workflows/daily-continuous-progress.yml` creates a daily issue used to drive incremental repository work and trigger the Copilot coding agent.

## Trigger Conditions

- Scheduled run: `0 9 * * *` (daily at 09:00 UTC)
- Manual run: `workflow_dispatch`

## Required Repository Secret

- `GH_PAT` (recommended): used to create issues/comments in a way that reliably triggers downstream automation and Copilot agent behavior.

If `GH_PAT` is missing, the workflow falls back to `GITHUB_TOKEN`. The workflow still runs, but trigger reliability is lower. The daily issue body includes a status line so maintainers can see which token path was used.

## Current Behavior

The workflow is intentionally idempotent:

1. Build title `Daily Progress: YYYY-MM-DD`.
2. Search open issues with `automation` and `continuous-progress` labels.
3. If today's issue already exists, **self-heal** it by ensuring:
   - required labels exist (`automation`, `continuous-progress`, `copilot`)
   - `@copilot` is assigned (best-effort; logs if assignment cannot be performed)
   - a single trigger comment exists with marker:
     `<!-- daily-progress-copilot-trigger -->`
4. If today's issue does not exist, create it, then apply the same self-heal checks.

This prevents duplicate daily issues and also avoids the failure mode where an existing issue silently skips Copilot triggering.

## Operational Notes

- Trigger comments are deduplicated with a hidden marker string.
- Workflow permissions include write access to contents, issues, and pull requests.
- The workflow should be paired with label/assignment automations for best results.
