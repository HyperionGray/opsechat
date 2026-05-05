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

Sanity checks:

```bash
python chat-room.py --help
python runserver_refactored.py test
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
python chat-room.py
```

That starts the app on `127.0.0.1:5000` by default.

## Tor Runtime

`chat-room.py --tor` and `runserver_refactored.py` both expect a reachable Tor
control port.

Example local Tor daemon:

```bash
tor --ControlPort 9051 --CookieAuthentication 1
```

Then start OpSecChat:

```bash
source .venv/bin/activate
python chat-room.py --tor
```

If you need strict Tor-only ingress/egress in the refactored runtime:

```bash
export OPSECHAT_REQUIRE_TOR=1
export OPSECHAT_FORCE_TOR_EGRESS=1
export TOR_CONTROL_HOST=127.0.0.1
export TOR_CONTROL_PORT=9051
export TOR_SOCKS_HOST=127.0.0.1
export TOR_SOCKS_PORT=9050
python runserver_refactored.py
```

## Container Install

Use this when you want a dedicated Tor container for the app runtime. The
compose stack also exposes a localhost-only admin proxy for operator access,
and that proxy stays off the Tor network.

```bash
./compose-up.sh
```

Current access points:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/chat`

Current container topology:

- `tor` and `opsechat` share the backend `opsechat-network`
- `admin-proxy` and `opsechat` share the frontend `admin-network`
- `admin-proxy` does not join the Tor backend network

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

- [quadlets/README.md](quadlets/README.md)
- [docs/setup/QUADLETS.md](docs/setup/QUADLETS.md)

## Extended Services

The default runtime is chat-focused. Mail features are disabled unless you
enable them explicitly.

```bash
export OPSECHAT_ENABLE_EXTENDED_SERVICES=1
python runserver_refactored.py test
```

Or enable only selected subsystems:

```bash
export OPSECHAT_ENABLE_EMAIL_STACK=1
export OPSECHAT_ENABLE_HTTP_MAIL=1
python runserver_refactored.py test
```

## Notes

- Prefer `.venv` inside the repo over a shared home-directory virtualenv.
- The maintained web paths are `/`, `/chat`, and `/health`.
- `runserver.py` still exists for legacy compatibility, but the current docs
  and container runtime target `runserver_refactored.py`.
