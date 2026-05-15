# OpSecChat Installation Reference

For the user-friendly walkthrough, see [`QUICKSTART.md`](../../QUICKSTART.md).
This file is the dry, complete reference: every supported install path,
every relevant environment variable, every helper script.

There is no `install.sh`. The legacy native installer was retired.

---

## 1. Project-local virtualenv (recommended for development)

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Optional Node deps for Playwright:

```bash
npm ci
npx playwright install
```

Sanity checks:

```bash
python bin/chat-room.py --help
python bin/runserver.py test          # binds 127.0.0.1:5001
curl http://127.0.0.1:5001/health
```

---

## 2. Self-hosted ad-hoc native runtime

Local-only:

```bash
source .venv/bin/activate
python bin/chat-room.py
# binds 127.0.0.1:5000
```

Tor hidden service (requires a local Tor with a control port):

```bash
# In a separate terminal:
tor --ControlPort 9051 --CookieAuthentication 1
```

```bash
source .venv/bin/activate
python bin/chat-room.py --tor
```

The CLI prints the operator console URL and the chat URL on the new
ephemeral hidden service. `Ctrl+C` removes the hidden service and
exits.

---

## 3. Compose stack (recommended for hosted deployment)

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
./compose-up.sh
```

The script auto-detects `podman compose`, `docker compose` (plugin),
or `podman-compose`. It brings up:

- `opsechat-tor` -- Tor daemon
- `opsechat-app` -- Flask app
- `opsechat-admin-proxy` -- Caddy on `127.0.0.1:8087` for the operator

Verify:

```bash
curl http://127.0.0.1:8087/health
```

Tear down:

```bash
./compose-down.sh
```

End-to-end test:

```bash
./scripts/test-compose-e2e.sh
```

For container details (image build, networks, volumes), see
[`DOCKER.md`](DOCKER.md).

---

## 4. Quadlets (systemd-managed Podman)

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
podman build -t localhost/opsechat:latest .
./install-quadlets.sh
systemctl --user start opsechat-app
```

Find the onion address:

```bash
journalctl --user -u opsechat-app -f | grep -i onion
```

Full reference: [`QUADLETS.md`](QUADLETS.md) and
[`../../quadlets/README.md`](../../quadlets/README.md).

---

## 5. Tor egress / ingress controls

| Variable                         | Default | Effect                                                                                  |
|----------------------------------|---------|-----------------------------------------------------------------------------------------|
| `OPSECHAT_REQUIRE_TOR`           | off     | Refuse to start without a published hidden service                                      |
| `OPSECHAT_FORCE_TOR_EGRESS`      | off     | Route outbound HTTP/SMTP/IMAP through the Tor SOCKS proxy                               |
| `TOR_CONTROL_HOST`               | 127.0.0.1 | Host of the Tor control port                                                          |
| `TOR_CONTROL_PORT`               | 9051    | Tor control port                                                                        |
| `TOR_SOCKS_HOST`                 | inherit | Tor SOCKS host (defaults to `TOR_CONTROL_HOST`)                                         |
| `TOR_SOCKS_PORT`                 | 9050    | Tor SOCKS port                                                                          |
| `OPSECHAT_TOR_STARTUP_TIMEOUT`   | 30      | Seconds to wait for the Tor control port at boot                                        |
| `OPSECHAT_TOR_RETRY_DELAY`       | 1       | Seconds between Tor control retries                                                     |

The compose stack sets all of these for you and runs the app with
`OPSECHAT_REQUIRE_TOR=1` and `OPSECHAT_FORCE_TOR_EGRESS=1`.

---

## 6. Extended (out-of-alpha) services

Off by default. See [`PROFILES.md`](PROFILES.md) for the full flag table
and [`../ALPHA_SCOPE.md`](../ALPHA_SCOPE.md) for what is in vs. out of
alpha. For alpha, leave these flags unset.

---

## 7. Notes

- Prefer `.venv` inside the repo over a shared home-directory venv.
- The maintained alpha web paths are `/`, `/chat`, `/health`,
  `/version`, `/chat/stats`, `/console`, `/console/api`, and
  `/dashboard`.
- The supported entrypoints are `bin/runserver.py` (production) and
  `bin/chat-room.py` (CLI / ad-hoc). There is no `runserver_refactored.py`.
