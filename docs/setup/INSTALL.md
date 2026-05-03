# Installation

There is no supported `install.sh` in this checkout.

Use one of these paths instead:

1. project-local virtualenv for local development and manual runtime checks
2. compose stack for a containerized Tor setup
3. quadlets for systemd-managed Podman deployment

## Recommended: Project-Local Virtualenv

This is the least confusing path when picking the repo back up.

```bash
cd /path/to/opsechat

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Optional frontend test dependencies:

```bash
npm ci
```

Runtime note:

`bin/*.py` are thin launchers for normal operator workflows; for example,
`bin/chat-room.py` launches the app while the core modules live in
`src/python/`.
For normal operator use, prefer the `bin/` launchers; use direct
`src/python/` entrypoints only for testing or advanced runtime checks.

Sanity checks:

```bash
python bin/chat-room.py --help
python src/python/runserver_refactored.py test
curl http://127.0.0.1:5001/health
```

Current local URLs in test mode:

- `http://127.0.0.1:5001/`
- `http://127.0.0.1:5001/chat`
- `http://127.0.0.1:5001/health`

## Simple Native Runtime

For the normal local web flow:

```bash
source .venv/bin/activate
python bin/chat-room.py
```

That starts the app on `127.0.0.1:5000` by default.

## Tor Runtime

Most operators should use the `bin/chat-room.py --tor` launcher. The
lower-level `src/python/runserver_refactored.py` runtime is for advanced
strict-Tor deployment checks and also expects a reachable Tor control port.

Example local Tor daemon:

```bash
tor --ControlPort 9051 --CookieAuthentication 1
```

Then start OpSecChat:

```bash
source .venv/bin/activate
python bin/chat-room.py --tor
```

If you need the advanced strict Tor-only ingress/egress runtime:

```bash
export OPSECHAT_REQUIRE_TOR=1
export OPSECHAT_FORCE_TOR_EGRESS=1
export TOR_CONTROL_HOST=127.0.0.1
export TOR_CONTROL_PORT=9051
export TOR_SOCKS_HOST=127.0.0.1
export TOR_SOCKS_PORT=9050
python src/python/runserver_refactored.py
```

## Container Install

Use this when you want Tor and the app isolated in containers.

```bash
./compose-up.sh
```

Current access points:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/chat`

Current helper commands:

```bash
./verify-setup.sh
./compose-down.sh
docker compose -f container-compose.yml logs opsechat
```

The helper scripts auto-detect `podman-compose`, `docker-compose`, or the
`docker compose` plugin.

## Quadlets

For systemd-managed Podman deployment, use:

- [../../quadlets/README.md](../../quadlets/README.md)
- [QUADLETS.md](QUADLETS.md)

## Extended Services

The default runtime is chat-focused. Mail features are disabled unless you
enable them explicitly.
