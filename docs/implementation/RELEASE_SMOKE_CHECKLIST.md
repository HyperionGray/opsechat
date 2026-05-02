# Release Smoke Checklist

Use this lightweight checklist before merging release-facing PRs.

## 1) Environment sanity

- [ ] `python3 -m pip install -r requirements.txt`
- [ ] `python3 -m pip install -r requirements-dev.txt`
- [ ] `npm ci` (if JS tests are part of the change)

## 2) Targeted validation

- [ ] Run targeted Python tests for touched modules, e.g.:
  - `python3 -m pytest tests/test_http_mail_routes_regression.py -q`
  - `python3 -m pytest tests/test_email_routes_admin.py -q`
- [ ] Run targeted Playwright tests when UI flows were changed

## 3) Baseline runner

- [ ] `bash run_tests.sh --skip-e2e` (or document why this cannot run in the current environment)

## 4) Release-path verification

- [ ] `/health` returns 200 with expected JSON keys (`status`, `version`, `service`)
- [ ] Core operator paths still respond (`/console`, `/<secret-path>/chat`, `/<secret-path>/mail`)
- [ ] No new broken links introduced in `README.md` / `docs/README.md`

## 5) PR hygiene

- [ ] Scope remains minimal and task-focused
- [ ] No secrets or local artifacts added
- [ ] Validation output (or blockers) captured in PR notes
