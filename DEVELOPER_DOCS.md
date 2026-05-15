# OpSecChat Developer Guide

You are about to change OpSecChat. Read [`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md)
first so you know what is in scope and what is fenced off. Then come back here.

---

## 1. Prerequisites

- Python 3.12+ (3.12.3 is the reference version on the dev VM).
- Node.js 20+ and npm.
- Optional but useful for local manual testing:
  - A local Tor daemon with a control port (`tor --ControlPort 9051 --CookieAuthentication 1`).
  - Podman 4+ (preferred) or Docker for the compose / quadlet flows.

The dev environment script `scripts/bootstrap-dev-environment.sh` codifies
the Python venv setup; the Node side is just `npm ci && npx playwright install`.

---

## 2. Repository layout

```
bin/                    # User-facing thin launchers (chat-room.py, runserver.py, ...)
src/python/             # Python application code
src/python/tui/         # Out-of-alpha TUI (kept for beta)
src/python/amazon_q/    # Out-of-alpha Amazon Q integration
src/web/templates/      # Jinja templates served by Flask
src/web/static/         # JS/CSS/asset files
containers/             # Dockerfile + Tor/Caddy configs
quadlets/               # Podman+systemd unit files
scripts/                # Helper bash scripts (compose-up/down, compose-e2e, ...)
tests/                  # pytest + Playwright alpha specs
tests/alpha/            # Alpha Playwright specs (real Flask app)
tests/legacy/           # Out-of-alpha Playwright specs (mock_server)
tests/manual/           # Throwaway diagnostic helpers, not CI
docs/                   # Long-form documentation
docs/setup/             # Deployment guides (compose, quadlets, Docker)
docs/user-guide/        # User-facing guides (alpha shipping ones live at repo root)
docs/development/       # Developer / contributor process docs
docs/assessment/        # Historical reviews; superseded by ALPHA_SCOPE.md for alpha
docs/ALPHA_SCOPE.md     # The authoritative alpha-vs-beta fence
```

The repo is intentionally flat. Each top-level directory has a single
clear job. New files go into the directory that already does that job;
do not invent siblings.

---

## 3. App factory and gating flags

Everything goes through `src/python/app_factory.py::create_app()`. The
factory:

1. Builds a Flask app pointing at `src/web/templates` and `src/web/static`.
2. Sets `app.secret_key` from `OPSECHAT_SECRET_KEY` or a fresh `token_urlsafe`.
3. Reads the gating flags below into `app.config`.
4. Initializes Flask-Limiter (with a fallback no-op if the module is missing).
5. Registers `add_security_headers` as the universal `after_request` hook.
6. Always registers the closed-roster chat routes.
7. Conditionally registers the gated route groups.
8. Always registers `mvp_routes` (operator console + service manifest).
9. Always registers `register_operational_routes(app)` (`/health`, `/version`,
   `/chat/stats`).

| Flag                                    | Default | Effect when set                                                          |
|-----------------------------------------|---------|--------------------------------------------------------------------------|
| `OPSECHAT_ENABLE_EXTENDED_SERVICES`     | off     | Implicit on for the three flags below                                    |
| `OPSECHAT_ENABLE_LEGACY_CHAT`           | off     | Registers `chat_routes` (legacy `/<secret>/...` drop-chat)               |
| `OPSECHAT_ENABLE_EMAIL_STACK`           | off     | Registers `email_routes` (SMTP/IMAP, burner emails, domain rotation)     |
| `OPSECHAT_ENABLE_HTTP_MAIL`             | off     | Registers `http_mail_routes`                                             |
| `OPSECHAT_ENABLE_REVIEWS`               | off     | Registers `review_routes`                                                |
| `OPSECHAT_REQUIRE_TOR`                  | off     | Refuse to start without a working Tor hidden service                     |
| `OPSECHAT_FORCE_TOR_EGRESS`             | off     | Route outbound HTTP/SMTP/IMAP through the Tor SOCKS proxy                |
| `MESSAGE_EXPIRY_SECONDS`                | 180     | Per-message TTL                                                          |
| `DM_EXPIRY_SECONDS`                     | 60      | One-shot DM TTL                                                          |
| `ROOM_INACTIVE_SECONDS`                 | 3600    | Room TTL after last activity                                             |
| `OPSECHAT_TOR_STARTUP_TIMEOUT`          | 30      | Seconds to wait for the Tor control port at boot                         |
| `OPSECHAT_TOR_RETRY_DELAY`              | 1       | Seconds between Tor control retries                                      |

Anything not listed is off by default. Adding a new feature should mean
adding a new flag, gating it off in alpha, and updating
[`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md) accordingly.

---

## 4. Where the closed-roster logic lives

Server side:

- `src/python/openpgp_room_policy.py` -- application-level RoomMember,
  RoomEpoch, roster canonicalization and hashing, TrustStore semantics.
- `src/python/closed_roster_room.py` -- `ClosedRosterState`: per-room
  immutable epoch storage and `validate_posted_envelope()`.
- `src/python/simple_chat_routes.py` -- the Flask blueprint: `/chat/...`
  routes, the `ChatRoom` in-memory storage with memory-overwrite
  cleanup, and the per-session sliding-window rate limiter.

Client side:

- `src/web/templates/simple_chat_room.html` -- the single-page room shell.
- `src/web/templates/simple_chat_index.html` -- the create-room landing.
- `src/web/static/chat-room.js` -- the heavyweight client: identity
  generation/import, key cache, decrypt+verify pipeline, send pipeline,
  trust-state UI, security-warning modal.
- `src/web/static/chat-index.js` -- the trivial create-room handler.
- `src/web/static/openpgp.min.js` -- vendored OpenPGP.js.

Operational endpoints (`/health`, `/version`, `/chat/stats`) are
registered by `app_factory.register_operational_routes()`. They MUST
stay stable; container healthchecks and external monitoring depend on
them. The version payload is `{service: "opsechat", version, timestamp}`.

---

## 5. Tor wiring

`src/python/tor_transport.py` is the single source of truth for Tor
egress and ingress configuration. The relevant bits:

- `resolve_tor_control_endpoint()` returns the host/port for stem.
- `tor_ingress_required()` reads `OPSECHAT_REQUIRE_TOR`.
- `tor_egress_enabled()` reads `OPSECHAT_FORCE_TOR_EGRESS`.
- `TorSMTP`, `TorIMAP4`, `TorIMAP4_SSL` -- SMTP/IMAP subclasses that
  open sockets through the Tor SOCKS proxy. Used by the email stack
  (out of alpha; gated off).

The Tor hidden-service publication itself happens in
`bin/runserver.py` (background thread) and `bin/chat-room.py`
(synchronous, with timeout).

---

## 6. Running the test suites

### 6.1 Python alpha tests (pytest)

```bash
source .venv/bin/activate
pytest -q
```

`pytest.ini` ignores the email/burner/HTTP-mail/domain-manager test
files by default. To run a specific out-of-alpha test, invoke it
directly:

```bash
pytest tests/test_email_system.py -q
```

### 6.2 Playwright alpha tests (real Flask app)

```bash
npm ci                       # one-time
npx playwright install       # one-time, downloads browsers
npx playwright test          # default = chromium-headless across alpha specs
```

The webServer block in `playwright.config.js` boots
`tests/real_app_server.py` (which is the actual `app_factory.create_app()`
on `127.0.0.1:5111`). All alpha specs hit the real app, not a mock.

#### Multi-browser headless (CI shape)

```bash
npm run test:alpha:headless
# or
npx playwright test --project=chromium-headless --project=firefox-headless --project=webkit-headless
```

#### Headed and slow-mo (manual review)

```bash
npm run test:alpha:headed     # visible chromium, real-time
npm run test:alpha:slowmo     # visible chromium, ~350ms slow-mo, narrated console output
```

The slow-mo project only runs `tests/alpha/visual_walkthrough.spec.js`,
which is the documented hosted-user flow with `console.log` narration.
Use this when you want to literally watch the alpha walkthrough happen
end-to-end before tagging a release.

### 6.3 Container-up-to-container-down

```bash
./scripts/test-compose-e2e.sh
```

This script:

1. `./compose-up.sh` (podman or docker auto-detected).
2. Polls `http://127.0.0.1:8080/health` until green or 180s timeout.
3. Runs the alpha Playwright specs against the admin proxy URL.
4. `./compose-down.sh` in an EXIT trap, so the stack tears down even on
   test failure.

This is the acceptance test for "the deployment story really works".

### 6.4 Legacy specs (out of alpha, opt-in)

```bash
npm run test:legacy
# or
npx playwright test --config=playwright-legacy.config.js
```

Legacy specs live in `tests/legacy/`, drive `tests/mock_server.py`,
and cover features not in alpha scope (legacy drop-chat, email,
burner, etc.). They exist for archaeological reference and will be
either rebuilt or retired during the beta cycle.

---

## 7. Adding a new route

1. Decide whether the route is alpha-shipping or extended-only. If
   alpha, register it unconditionally in `app_factory.create_app()`.
   If extended, gate it behind a new `OPSECHAT_ENABLE_*` flag and
   leave it off by default.
2. Put the route handler in an existing blueprint module if one fits.
   Otherwise create a new `_routes.py` module under `src/python/`.
3. Add at least one alpha Playwright spec that exercises the route end
   to end. If the route is purely server-side, add a request-fixture
   spec under `tests/alpha/`. If it has UI, add a browser spec.
4. Update [`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md) to list the
   new surface in the appropriate table.
5. Update `mvp_routes._build_manifest()` so the operator console
   advertises the new service.

---

## 8. Adding a new test

- Pytest: drop a `test_*.py` file in `tests/`. It is automatically
  picked up. If the new file depends on a flag-gated module, add it
  to `pytest.ini`'s `--ignore=` list so the default invocation stays
  green for fresh checkouts.
- Playwright (alpha): drop a `<name>.spec.js` file in `tests/alpha/`.
  It will be picked up by the default `playwright.config.js`
  `testMatch`.
- Playwright (legacy / out-of-alpha): drop the spec in
  `tests/legacy/`. It will only run via the explicit
  `playwright-legacy.config.js`.

---

## 9. Style and constraints

- `rules.json` rules apply: no emojis in shipped UI / CLI text, no demo
  data mixed into production paths, prefer Podman over Docker, prefer
  Playwright for web validation.
- Security headers are mandatory. If you add a route, the universal
  `after_request` hook will set them; do not strip them.
- Python imports: `src/python/` is on `sys.path` via the bin launchers
  and `tests/conftest.py`. Do not invent additional package roots.
- Keep `/health` cheap. Do not add expensive checks behind it.
- Keep `/version` payload stable: `{service, version, timestamp}`.

---

## 10. Release checklist

Before tagging an alpha:

1. `pytest -q` green.
2. `npx playwright test` green across chromium/firefox/webkit.
3. `./scripts/test-compose-e2e.sh` green on a host with podman or docker.
4. `npm run test:alpha:slowmo` watched end-to-end at least once.
5. Manually walk every command in [`QUICKSTART.md`](QUICKSTART.md) for
   each persona on a clean checkout.
6. Update `VERSION` and `package.json` if bumping the release tag.
7. Push to `master`, tag, push the tag.

---

## 11. Where the bodies are buried

- `src/python/utils.py::id_generator` uses `random` (not `secrets`)
  intentionally for ephemeral session ids; do not "fix" this without
  thinking. Cryptographic ids (room ids, DM ids) use `secrets.token_urlsafe`.
- `simple_chat_routes.py` keeps a per-room legacy `room_key` token for
  backward-compat with older tests. The token is **inert**; the
  closed-roster crypto does not use it.
- `monitoring.py::get_version_info()` is the canonical version payload.
  The earlier inline `/version` route in `app_factory.py` referenced a
  non-existent `get_version_info` symbol; that has been fixed and the
  route now goes through `register_operational_routes()`.
- The TUI (`bin/tui-*.py`, `src/python/tui/`) speaks raw TCP and does
  not share the closed-roster crypto. It ships in the repo for beta
  follow-up but is not part of the alpha surface.
