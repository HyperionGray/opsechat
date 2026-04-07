# Automation Consolidation Summary

## Overview
This document tracks the current automation baseline and the latest cleanup pass for CI and repository hygiene.

## 2026-04-07 Scheduled Maintenance Update

### Implemented feature: consolidated CI workflow
Added **`.github/workflows/ci.yml`** with three branch-protection-friendly checks:

- `python-tests` (gate job over Python 3.10/3.11/3.12 matrix)
- `playwright-e2e`
- `security-baseline` (pip-audit and npm audit)

The workflow includes:

- explicit minimal permissions
- concurrency cancellation for duplicate PR/ref runs
- per-job timeouts
- reuse of composite setup actions in `.github/actions/`

### Repository cleanup completed
Removed stale tracked artifacts and placeholders:

- root backup files: `Dockerfile~HEAD`, `docker-compose.yml~HEAD`
- accidental placeholder files under `.github/.github/workflows/`
- empty placeholder `.github/d`
- tracked `.bish-index` artifacts across multiple directories
- obsolete ad-hoc scripts: `test-ci-fix.js`, `test-server.js`

## Current Workflow Inventory

As of this update, `.github/workflows` contains **20** workflow files.

- Push and/or PR triggered workflows: **7**
- Scheduled workflows: **5**
- Manual (`workflow_dispatch`) workflows: **11**

Note: several workflows are intentionally specialized (label/review/security automation). The new `ci.yml` is the primary quality gate for core build/test/security validation.

## Follow-up Actions

1. Update branch protection rules to require:
   - `python-tests`
   - `playwright-e2e`
   - `security-baseline`
2. Validate `ci.yml` behavior on a live PR run and verify cache hits.
3. Review legacy automation workflows and remove or retarget any redundant triggers.
