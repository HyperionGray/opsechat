# Developer Quickstart

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- Tor available locally for Tor-mode runtime checks
- Podman or Docker for container validation

## Local Setup

```bash
cd /path/to/opsechat

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
```

## Fast Validation Loop

```bash
python -m pytest \
  tests/test_openpgp_room_policy.py \
  tests/test_chat_endpoints.py \
  tests/test_simple_chat_routes.py \
  tests/test_rate_limit_and_health.py

python -m pytest \
  tests/test_container_deployment.py \
  tests/test_installer.py \
  tests/test_mvp_console.py
```

## Run The App Locally

### Predictable local debug mode

```bash
python runserver_refactored.py test
```

Useful checks:

```bash
curl -i http://127.0.0.1:5001/health
curl -i http://127.0.0.1:5001/
curl -i http://127.0.0.1:5001/chat
```

### Simple web launcher

```bash
python chat-room.py
```

### Tor mode

```bash
tor --ControlPort 9051 --CookieAuthentication 1
python chat-room.py --tor
```

## Container Validation

```bash
./compose-up.sh
./verify-setup.sh
./compose-down.sh
```

## Full Test Commands Already In The Repo

```bash
python -m pytest
npx playwright test
python pf-tasks/test.py --skip-e2e
```

## Files To Know

- `chat-room.py` - simplest maintained web launcher
- `runserver_refactored.py` - local debug/test entrypoint
- `app_factory.py` - Flask app creation and route registration
- `simple_chat_routes.py` - `/chat` endpoints and room lifecycle
- `closed_roster_room.py` - immutable roster state and envelope validation
- `mvp_routes.py` - `/` and `/console`
- `monitoring.py` - `/health` payload generation
- `container-compose.yml` - local multi-container deployment
- `containers/Dockerfile` - container build and runtime command

## Maintenance Notes

- Keep `/health` stable and lightweight; deployment checks rely on it.
- When changing room bootstrap or envelope validation, update the focused chat tests first.
- When changing compose or container behavior, update `tests/test_container_deployment.py`.
- Review `README.md`, `INSTALL.md`, and `QUICKSTART.md` whenever an entrypoint changes.
