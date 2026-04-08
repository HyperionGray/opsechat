# GitHub Automation Notes

This directory contains GitHub-specific automation assets:

- `workflows/` for active workflows used by this repository
- `actions/` for reusable local composite actions
- `workflow-templates/` for template references

## Repository Hygiene Audit

A scheduled workflow (`repository-hygiene-audit.yml`) runs every 3 hours to:

1. detect unfinished markers in source/config files,
2. flag likely stray or merge-backup files,
3. flag unexpected empty files,
4. report nested duplicate directory structures.

The workflow uses `scripts/repo_hygiene_audit.py`, uploads markdown/json artifacts, and creates or updates a tracking issue when findings exist.

