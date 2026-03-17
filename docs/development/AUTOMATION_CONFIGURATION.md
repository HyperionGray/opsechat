# Automation Configuration Guide

This guide documents the repository variables and manual inputs used by the automation workflows.

## Why this exists

Several automation workflows previously hardcoded labels, assignees, and comments. The workflows now support centralized configuration through repository variables so behavior can be changed without editing workflow files.

## Repository variables

Configure these in GitHub: `Settings -> Secrets and variables -> Actions -> Variables`.

### Issue automation

- `DEFAULT_ISSUE_LABELS`
  - Used by: `auto-label.yml`
  - Format: comma-separated labels
  - Default: `triage,copilot`
  - Example: `triage,needs-investigation,copilot`

### PR automation

- `DEFAULT_PR_ASSIGNEES`
  - Used by: `auto-assign-pr.yml`
  - Format: comma-separated GitHub usernames
  - Default: `copilot`
  - Example: `copilot,octocat`

- `DEFAULT_PR_REVIEW_LABELS`
  - Used by: `auto-label-comment-prs.yml`
  - Format: comma-separated labels
  - Default: `needs-review,copilot`

- `DEFAULT_PR_REVIEW_COMMENT`
  - Used by: `auto-label-comment-prs.yml`
  - Format: plain text
  - Default: `Thanks for the PR! Copilot will assist with review.`

### Daily progress automation

- `DAILY_PROGRESS_LABELS`
  - Used by: `daily-continuous-progress.yml`
  - Format: comma-separated labels
  - Default: `automation,continuous-progress,copilot`

- `DAILY_PROGRESS_ASSIGNEES`
  - Used by: `daily-continuous-progress.yml`
  - Format: comma-separated GitHub usernames
  - Default: `copilot`

- `DAILY_PROGRESS_TRIGGER_MENTION`
  - Used by: `daily-continuous-progress.yml`
  - Format: mention text
  - Default: `@copilot`

- `DAILY_PROGRESS_COMMENT_TEMPLATE`
  - Used by: `daily-continuous-progress.yml`
  - Format: plain text template
  - Default: empty (uses built-in checklist prompt)
  - Optional placeholders:
    - `{{MENTION}}`
    - `{{FOCUS_AREA}}`
    - `{{EXTRA_INSTRUCTIONS}}`

## Manual workflow dispatch inputs

`daily-continuous-progress.yml` supports these `workflow_dispatch` inputs:

- `focus_area` (string, optional)
  - Adds a focus area to the issue body and Copilot prompt.
- `extra_instructions` (string, optional)
  - Adds extra instructions to the issue body and Copilot prompt.
- `force_new_issue` (boolean, default `false`)
  - If `false`, the workflow reuses today's issue.
  - If `true`, the workflow creates a new issue for the current run.

## Notes

- If today's issue already exists and `force_new_issue` is `false`, the workflow exits early.
- If manual inputs are provided while reusing today's issue, the workflow posts a follow-up comment with the extra context.
- If a required list variable is empty after parsing, the workflow logs and safely skips or fails where appropriate.
