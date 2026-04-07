# TODO: Automation Consolidation Follow-up

## Completed ✅
- Created composite actions for Python and Node/Playwright setup
- Created consolidated CI workflow (ci.yml)
- Removed 13 noisy workflows that triggered on every push/PR
- Updated security scan to run bi-weekly instead of weekly
- Removed push/PR triggers from scheduled workflows
- Added concurrency controls to prevent duplicate runs
- Created comprehensive documentation
- Restored missing reusable workflows: `python-tests.yml`, `playwright-tests.yml`, `security-scan.yml`
- Restored `workflows-sync.yml` in `.github/workflows/`
- Removed stale duplicate workflow `auto-sec-scan.yml`
- Removed stale placeholder workflow files under `.github/.github/workflows/`
- Removed stale root backup artifacts (`Dockerfile~HEAD`, `docker-compose.yml~HEAD`)

## Still To Do

### 1. Branch Protection Rules (IMPORTANT)
- [ ] Update branch protection settings in GitHub to require the new `ci.yml` jobs:
  - `python-tests` 
  - `playwright-e2e`
  - `security-baseline`
- [ ] Remove old workflow requirements from branch protection if they exist
- [ ] This must be done via GitHub UI or API (cannot be done via workflow files)

### 2. Testing and Verification
- [ ] Create a test PR to verify the CI workflow runs successfully
- [ ] Verify that only ONE Playwright run occurs per PR (not multiple)
- [ ] Check that caches are being hit (look for cache hit messages in Actions logs)
- [ ] Confirm no redundant workflow runs are happening on PRs
- [ ] Test label-triggered workflows still activate correctly:
  - Add a label to a PR and verify `auto-llm-pr-review.yml` runs
  - Add a label to an issue and verify `auto-llm-issue-review.yml` runs

### 3. Potential Optimizations
- [ ] Consider whether `playwright-tests.yml` and `python-tests.yml` should be kept or deprecated
  - Currently they're callable via `workflow_call` but not directly triggered
  - Could inline them into `ci.yml` if they're not used elsewhere
- [ ] Review if any of the removed workflows in `bak/workflows-removed/` should be converted to manual/label-triggered
- [ ] Consider adding more comprehensive security checks to the CI baseline if needed

### 4. Documentation Updates
- [x] Update repository README or contributing guide to mention the new CI workflow
- [ ] Document the label-based triggering system for team members
- [ ] Add instructions on how to manually trigger scheduled workflows if needed

### 5. Monitoring
- [ ] Monitor CI run times over the next week to ensure they're faster
- [ ] Watch for any missing checks or unexpected behavior
- [ ] Check GitHub Actions usage/costs to confirm reduction

## Notes
- The bi-weekly cron for security scan runs on 1st and 3rd Sunday of each month (approximately every 2 weeks)
- All workflows now have proper timeouts to prevent runaway jobs
- Concurrency groups will automatically cancel redundant runs
- Composite actions enable consistent environment setup across all workflows
