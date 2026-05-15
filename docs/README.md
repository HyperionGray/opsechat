# OpSecChat Documentation

The four alpha-shipping docs are at the **repo root** because they are
the ones a brand-new reader needs first:

- [`README.md`](../README.md) -- one-page project overview, alpha-scope
  summary, and links into the rest.
- [`QUICKSTART.md`](../QUICKSTART.md) -- shell-by-shell walkthrough for
  the three deployment personas (self-hosted ad-hoc, compose, quadlets).
- [`USER_DOCS.md`](../USER_DOCS.md) -- everything a user does in the
  browser once they have a room URL.
- [`DEVELOPER_DOCS.md`](../DEVELOPER_DOCS.md) -- repo layout, app
  factory, gating flags, and how to run all three test suites.

The fence between alpha and beta lives at:

- [`ALPHA_SCOPE.md`](ALPHA_SCOPE.md) -- the authoritative in/out list.
  If a feature is referenced by the alpha-shipping docs above without
  being listed here, that is a bug.

---

## Long-form references

### Setup
- [`setup/INSTALL.md`](setup/INSTALL.md) -- complete install matrix.
- [`setup/PROFILES.md`](setup/PROFILES.md) -- environment-flag reference.
- [`setup/DOCKER.md`](setup/DOCKER.md) -- container image and stack details.
- [`setup/QUADLETS.md`](setup/QUADLETS.md) -- systemd quadlet reference.

### User guide (legacy / out-of-alpha topics)

The alpha user guide lives at [`USER_DOCS.md`](../USER_DOCS.md). The
documents below cover features that are out of alpha scope (kept for
beta follow-up); read them only if you have explicitly enabled the
matching `OPSECHAT_ENABLE_*` flag.

- [`user-guide/SIMPLE_CHAT_ROOMS.md`](user-guide/SIMPLE_CHAT_ROOMS.md)
- [`user-guide/EMAIL_SYSTEM.md`](user-guide/EMAIL_SYSTEM.md)
- [`user-guide/EMAIL_QUICKSTART.md`](user-guide/EMAIL_QUICKSTART.md)
- [`user-guide/PGP_USAGE.md`](user-guide/PGP_USAGE.md)
- [`user-guide/TUI_README.md`](user-guide/TUI_README.md)
- [`user-guide/TUI_QUICKSTART.md`](user-guide/TUI_QUICKSTART.md)
- [`user-guide/TESTING.md`](user-guide/TESTING.md)

### Development
- [`development/CONTRIBUTING.md`](development/CONTRIBUTING.md)
- [`development/CODE_OF_CONDUCT.md`](development/CODE_OF_CONDUCT.md)
- [`development/DEVELOPMENT.md`](development/DEVELOPMENT.md)
- [`development/RELEASE_TODO.md`](development/RELEASE_TODO.md)
  (superseded for alpha by [`ALPHA_SCOPE.md`](ALPHA_SCOPE.md))

### Assessment / history
- [`assessment/ALPHA_READINESS_ASSESSMENT.md`](assessment/ALPHA_READINESS_ASSESSMENT.md)
  (historical; superseded by [`ALPHA_SCOPE.md`](ALPHA_SCOPE.md))
- [`assessment/SECURITY_ASSESSMENT.md`](assessment/SECURITY_ASSESSMENT.md)
- Other historical reviews under `assessment/`.

### Security
- [`SECURITY.md`](SECURITY.md) -- the operating security model.

### Legal (drafts; require legal review before any public deployment)
- [`legal/ACCEPTABLE_USE_POLICY.md`](legal/ACCEPTABLE_USE_POLICY.md)
- [`legal/TERMS_OF_SERVICE.md`](legal/TERMS_OF_SERVICE.md)
