# TODO: Automation Consolidation Follow-up

This document mirrors the root-level `TODO-automation.md` for consistency with other implementation docs.

## Completed
- Created composite actions for Python and Node/Playwright setup
- Created consolidated CI workflow (`ci.yml`)
- Removed noisy workflows that triggered on every push/PR
- Updated security scan cadence
- Added concurrency controls to prevent duplicate runs

## Still To Do

### 1. Branch protection rules
- [ ] Require the consolidated `ci.yml` jobs in GitHub branch protection
- [ ] Remove any stale required checks from old workflows

### 2. Testing and verification
- [ ] Create a test PR and verify the consolidated workflow behavior
- [ ] Confirm only one Playwright run per PR
- [ ] Confirm cache utilization in workflow logs

### 3. Optimization decisions
- [ ] Decide whether standalone workflow-call files remain necessary
- [ ] Review removed workflows under `bak/workflows-removed/` for manual/label use

### 4. Documentation follow-up
- [ ] Update contributor docs with the current CI flow
- [ ] Document label-triggered automation behavior

### 5. Monitoring
- [ ] Monitor CI duration and check usage/cost trends
