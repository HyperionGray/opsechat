# Changelog - Automation Consolidation

## 2026-03-01 - Workflow Consolidation

### Summary
Major cleanup and consolidation of GitHub Actions workflows to reduce automation noise and improve CI/CD reliability.

### Statistics
- **Before**: 33 workflows, 16 auto-triggered on every PR/push
- **After**: 22 workflows, 3 auto-triggered on PR/push
- **Reduction**: 33% fewer workflows, 81% reduction in noisy automation

### Added
1. **Composite Actions** for code reuse:
   - `.github/actions/setup-python/action.yml` - Python environment with caching
   - `.github/actions/setup-node-playwright/action.yml` - Node.js and Playwright with browser caching

2. **Consolidated CI Workflow**:
   - `.github/workflows/ci.yml` - Single required CI workflow running:
     - Python tests (3.10, 3.11, 3.12)
     - Playwright E2E tests
     - Security baseline (pip-audit, npm audit)
   - Features: concurrency controls, proper timeouts, explicit permissions

3. **Documentation**:
   - `docs/AUTOMATION_CONSOLIDATION.md` - Complete consolidation documentation
   - `TODO-automation.md` - Follow-up tasks checklist

### Modified
1. **Refactored for Reusability**:
   - `playwright-tests.yml` - Now uses composite actions, callable via workflow_call
   - `python-tests.yml` - Now uses composite actions, callable via workflow_call

2. **Scheduled to Reduce Noise**:
   - `security-scan.yml` - Bi-weekly schedule (1st & 3rd Sunday), removed PR/push triggers
   - `auto-complete-cicd-review.yml` - Removed PR/push triggers (kept 12h schedule)

3. **Fixed**:
   - `workflows-sync.yml` - Restored proper sync configuration

### Removed (moved to bak/workflows-removed/)
13 workflows that created excessive noise by auto-triggering on every push/PR:
1. `amazon-q-review.yml`
2. `amazon-q-security-scan.yml`
3. `auto-amazonq-review.yml`
4. `auto-copilot-functionality-docs-review.yml`
5. `auto-copilot-org-playwright-loop.yaml`
6. `auto-copilot-org-playwright-loopv2.yaml`
7. `auto-copilot-org-playwright-loopv2.yml`
8. `auto-copilot-playwright-auto-test.yml` (deprecated)
9. `auto-copilot-test-review-playwright.yml`
10. `auto-gpt5-implementation.yml`
11. `auto-label-comment-prs.yml`
12. `auto-sec-scan.yml` (duplicate)
13. `test.yml` (duplicate)

### Remaining Workflows (22)

#### Core CI/Testing (5)
- `ci.yml` ⭐ NEW - Required CI workflow
- `playwright-tests.yml` - Reusable via workflow_call
- `python-tests.yml` - Reusable via workflow_call
- `security-scan.yml` - Bi-weekly scheduled
- `workflows-sync.yml` - Daily sync

#### Event-Triggered (5)
- `auto-assign-pr.yml` - On PR open
- `auto-assign-copilot.yml` - On issue label
- `auto-llm-pr-review.yml` - On PR label
- `auto-llm-issue-review.yml` - On issue label
- `auto-label.yml` - On issue open

#### Scheduled/Manual (12)
- `autonomous-progress.yml` - Every 6h
- `auto-advance-ball.yml` - Every 6h
- `auto-complete-cicd-review.yml` - Every 12h
- `auto-copilot-code-cleanliness-review.yml` - Every 12h
- `auto-close-issues.yml` - Weekly
- `auto-tag-based-review.yml` - On tags
- `auto-bug-report.yml` - Manual
- `auto-feature-request.yml` - Manual
- `copilot-instructions.yml` - Manual
- `standardize-labels.yml` - Manual
- `trigger-all-repos.yml` - Manual
- `workflows-sync-template-backup.yml` - Daily

### Benefits
1. **Faster CI**: Concurrency controls prevent duplicate workflow runs
2. **Consistent Setup**: Composite actions ensure identical environment configuration
3. **Reduced Noise**: 81% fewer auto-triggered workflows on PRs
4. **Better Caching**: Centralized caching for pip, npm, and Playwright browsers
5. **Easier Maintenance**: Setup changes in one place (composite actions)
6. **Lower Costs**: Significantly fewer workflow runs
7. **Security**: All workflows follow least-privilege with explicit permissions

### Security
- ✅ CodeQL analysis passed (0 alerts)
- ✅ All workflows have explicit GITHUB_TOKEN permissions
- ✅ No vulnerabilities introduced

### Follow-Up Required
See `TODO-automation.md` for:
- Updating branch protection rules to require new CI workflow
- Testing CI on a real PR
- Monitoring workflow performance

### References
- Issue: "Automation: Direction"
- Requirements: Per P4X-ng comment - keep only triggered workflows, fix continuous progress, bi-weekly security, keep sync
- Full Documentation: `docs/AUTOMATION_CONSOLIDATION.md`

## 2026-04-04 - Scheduled hardening and cleanup

### Summary
- Implemented CSP nonce-based script hardening in the Flask app factory.
- Updated active templates to use nonce-tagged scripts and removed inline script event handlers in active paths.
- Cleaned stale repository artifacts discovered during scheduled maintenance.

### Added
- `docs/implementation/CSP_NONCE_HARDENING_2026-04-04.md` documenting the implementation and follow-up direction.

### Changed
- `app_factory.py` now issues per-request `csp_nonce` and injects it into templates.
- `Content-Security-Policy` updated to enforce:
  - `script-src 'self' 'nonce-...'`
  - `script-src-attr 'none'`
  - `object-src 'none'`
  - `base-uri 'self'`
  - `form-action 'self'`
- Active templates now bind events via JavaScript listeners rather than inline HTML handlers.

### Removed
- Deleted stale files:
  - `docker-compose.yml~HEAD`
  - `Dockerfile~HEAD`
  - `test-ci-fix.js`
  - `test-server.js`
  - `templates/email_burner_old.html`

### Tests
- Updated CSP/security-header tests to validate nonce-compatible strict script behavior.
