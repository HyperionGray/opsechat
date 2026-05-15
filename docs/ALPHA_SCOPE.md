# OpSecChat Alpha Scope

This is the authoritative fence between what is in scope for the
`0.8.0-alpha` release and what is explicitly punted to a later beta. If a
feature is not listed in **§1 In alpha** below, it is not part of alpha
even if it exists in the repo.

If you find any reference in the alpha-shipping docs (`README.md`,
`QUICKSTART.md`, `USER_DOCS.md`, `DEVELOPER_DOCS.md`) to something not
listed in §1, that is a bug -- open an issue.

---

## 1. In alpha

### 1.1 Surfaces (must work, must be documented, must be tested)

| Surface                | Path / endpoint                                                                 |
|------------------------|---------------------------------------------------------------------------------|
| Operator console       | `/`, `/console`, `/console/api`, `/dashboard`                                   |
| Closed-roster chat     | `/chat`, `/chat/create`                                                         |
| Closed-roster room     | `/chat/room/<id>`, `/chat/room/<id>/state`, `/chat/room/<id>/state/bootstrap`   |
| Room messages          | `/chat/room/<id>/messages` (GET, POST)                                          |
| Deprecation sentinel   | `/chat/room/<id>/key` (returns `410 Gone`, points to `/state`)                  |
| One-shot DM            | `/chat/dm/send` (POST), `/chat/dm/<id>` (GET)                                   |
| Key-management shell   | `/keys` (in-room key UI is the real workflow; this is just a pointer page)      |
| Operational endpoints  | `/health`, `/version`, `/chat/stats`                                            |
| Static assets          | `/static/openpgp.min.js`, `/static/chat-room.js`, `/static/chat-index.js`, `/static/simple-chat-*.css`, `/static/mvp-console.css` |

### 1.2 Deployment modes

| Mode                       | Tooling                                                                          | Persona                              |
|----------------------------|----------------------------------------------------------------------------------|--------------------------------------|
| Compose (podman/docker)    | `./compose-up.sh`, `./compose-down.sh`, `container-compose.yml`, `containers/*`  | Hosted-admin                         |
| Quadlets (systemd/Podman)  | `./install-quadlets.sh`, files under `quadlets/`                                 | Hosted-admin (production-leaning)    |
| Self-hosted ad-hoc         | `python bin/chat-room.py [--tor] [--port N] [--host H]`                          | Self-hosted user                     |
| Test mode (no Tor)         | `python bin/runserver.py test`                                                   | Developer                            |

### 1.3 Security properties enforced in alpha

- Closed roster locked at epoch 1; the active roster is **immutable**.
- All room messages are signed by the sender's OpenPGP key and encrypted to
  the **full** roster. Wildcard / anonymous recipients are rejected.
- Server validates every envelope: room id, epoch, roster hash, sender
  membership, recipient set, and recipient key id set. Rejected envelopes
  return `400` with a `error` JSON field naming the failure.
- Browser also validates everything server-side validates **plus** packet
  recipient key ids and verified signature key id.
- Per-message and per-DM TTL with explicit memory overwrite before delete.
- Per-session sliding-window rate limit on creates, messages, and DMs.
- Strict `Content-Security-Policy`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.

### 1.4 Test coverage gates for alpha

A green CI run requires:

| Suite                                          | Command                                       |
|------------------------------------------------|-----------------------------------------------|
| Python unit / route tests                      | `pytest -q`                                   |
| Playwright (real Flask app) -- headless        | `npx playwright test`                         |
| Compose container-up-to-container-down E2E     | `./scripts/test-compose-e2e.sh`               |

A green local manual-review pass also requires:

| Suite                                          | Command                                                |
|------------------------------------------------|--------------------------------------------------------|
| Headed slow-mo visual walkthrough              | `npm run test:alpha:slowmo`                            |

---

## 2. Out of alpha (punted to beta)

These features still exist in the repo because removing working code is
high-risk and not the point of this release. They are gated off by default,
not advertised in the alpha console, not documented in alpha docs, and not
exercised by alpha tests.

| Feature                | Code path                                                                  | Gating flag                              | Beta TODO                                                                 |
|------------------------|----------------------------------------------------------------------------|------------------------------------------|---------------------------------------------------------------------------|
| Email stack            | `src/python/email_*.py`, `src/python/domain_*.py`, `bin/domain-rotation.py`| `OPSECHAT_ENABLE_EMAIL_STACK=1`          | Spam filtering, second registrar API, abuse handling, real send tests     |
| HTTP mail              | `src/python/http_mail_*.py`                                                | `OPSECHAT_ENABLE_HTTP_MAIL=1`            | End-to-end user testing, recipient address-discovery story, retention UX  |
| Reviews                | `src/python/review_routes.py`                                              | `OPSECHAT_ENABLE_REVIEWS=1`              | Decide whether reviews are part of the product at all                     |
| Legacy drop-chat       | `src/python/chat_routes.py`, `src/python/landing_routes.py`                | `OPSECHAT_ENABLE_LEGACY_CHAT=1`          | Either retire or migrate behind closed-roster                             |
| TUI client/server      | `bin/tui-*.py`, `src/python/tui/`                                          | (separate process; no flag)              | Bring under closed-roster crypto; wire into the alpha doc set             |
| Amazon Q integration   | `src/python/amazon_q/`                                                     | (build-time)                             | Decide whether this stays as part of the supported pipeline               |
| AWS deployment         | (no changes here in alpha)                                                 | --                                       | Refresh once compose + quadlet deployments stabilize                      |

---

## 3. Explicitly retired in this pass

- `src/python/runserver_refactored.py` -- duplicate of `runserver.py`.
- `tests/e2e.spec.js.deprecated` -- already marked dead by name.
- `INSTALL.md` at repo root -- duplicate of `docs/setup/PROFILES.md`.
- All emoji glyphs from alpha-surface UI and CLI banners (per `rules.json`
  output-formatting rule).

---

## 4. Known alpha gaps (acceptable for this release; documented in user docs)

These are real limitations the user will notice. They are intentional for
alpha and are tracked for beta.

1. **No epoch 2.** Membership changes (add, remove, key rotation) require
   creating a new room. The UI says so explicitly. See `USER_DOCS.md` ->
   "Alpha caveats".
2. **Browser is the crypto owner.** The local OpenPGP private key lives in
   the browser session and (when the user explicitly downloads it) on disk.
   The server never sees private keys. There is no native key owner yet.
3. **No intended-recipient packet subpacket verification.** Recipient set is
   verified by explicit key-id checks, which is strong but does not match
   the full RFC 4880bis intended-recipient design.
4. **Retention windows are global, not per-room.** Messages: 180s. Rooms:
   1h idle. DMs: 60s. These are configurable via env (`MESSAGE_EXPIRY_SECONDS`,
   `ROOM_INACTIVE_SECONDS`, `DM_EXPIRY_SECONDS`) but not per-room.

---

## 5. Beta TODO summary (forward-looking)

The list below is not exhaustive; it captures the well-known follow-ups so
they do not get forgotten.

1. Signed epoch-transition workflow (epoch 2+).
2. Native (TUI / desktop) key owner outside the browser.
3. Intended-recipient subpacket support.
4. Negative-path browser tests for changed-key alarm scenarios.
5. Email stack hardening (registrar #2, spam filter, abuse policy).
6. HTTP mail end-to-end UX validation.
7. Decide TUI's place in the product (retire, fold, or re-implement under
   closed-roster crypto).
8. Per-room retention controls and operator-visible audit of cleanup.
9. Refresh AWS deployment doc after compose + quadlet stabilize.

---

**Owner:** OpSecChat maintainers.
**Last reviewed:** alpha cut.
