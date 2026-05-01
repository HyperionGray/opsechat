# OpSecChat

Ephemeral text chat over local HTTP or Tor, with an operator console at `/`,
room creation at `/chat`, and in-memory-only message storage.

**Version:** `0.8.0-alpha`  
**Primary docs:** [INSTALL.md](INSTALL.md), [QUICKSTART.md](QUICKSTART.md), [docs/README.md](docs/README.md)

## Current State

- The supported web entrypoints are `chat-room.py` and `runserver_refactored.py`.
- The simplest local startup path is `python chat-room.py`.
- The operator console lives at `/`.
- Chat rooms live at `/chat`.
- Health is exposed at `/health`.
- `install.sh` is gone from this checkout. Use a project-local virtualenv or the container stack.
- Extended mail and HTTP-mail routes are off by default and must be enabled with env flags.

## Fastest Start

```bash
git clone <repo-url>
cd opsechat

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt

python chat-room.py
```

Open:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/chat`
- `http://127.0.0.1:5000/health`

## Tor Mode

If you want an ephemeral onion service instead of localhost:

```bash
tor --ControlPort 9051 --CookieAuthentication 1

source .venv/bin/activate
python chat-room.py --tor
```

The launcher prints the onion URLs for both `/` and `/chat`.

## Container Stack

```bash
./compose-up.sh
```

What you get:

- Tor container
- app container
- localhost-only admin proxy at `http://127.0.0.1:8080/`

Useful commands:

```bash
./verify-setup.sh
./compose-down.sh
docker compose -f container-compose.yml logs opsechat
```

The current compose helpers detect `podman-compose`, `docker-compose`, or the
`docker compose` plugin.

## Which Entry Point?

- `chat-room.py`: simplest web launcher for localhost or `--tor`
- `runserver_refactored.py test`: local debug/test mode on port `5001`
- `tui-server.py` / `tui-client.py`: terminal-only chat flow
- `container-compose.yml`: multi-container runtime with Tor and localhost proxy

## Optional Services

The default profile is chat-only. To expose the mail stack locally:

```bash
export OPSECHAT_ENABLE_EXTENDED_SERVICES=1
python runserver_refactored.py test
```

Or enable components separately:

```bash
export OPSECHAT_ENABLE_EMAIL_STACK=1
export OPSECHAT_ENABLE_HTTP_MAIL=1
python runserver_refactored.py test
```

## Repository Map

- `chat-room.py`: web launcher with `--tor`, `--host`, and `--port`
- `runserver_refactored.py`: refactored Flask entrypoint
- `app_factory.py`: route wiring and app config
- `simple_chat_routes.py`: `/chat` API and room logic
- `closed_roster_room.py`: immutable room bootstrap and envelope validation
- `mvp_routes.py`: operator console at `/` and `/console`
- `containers/` and `container-compose.yml`: container runtime
- `scripts/`: compose helpers, verification, bootstrap
- `tests/`: pytest and Playwright coverage

## Docs

- [INSTALL.md](INSTALL.md): supported install paths
- [QUICKSTART.md](QUICKSTART.md): basic usage
- [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md): local dev loop
- [docs/setup/DOCKER.md](docs/setup/DOCKER.md): container runtime details
- [docs/user-guide/TUI_QUICKSTART.md](docs/user-guide/TUI_QUICKSTART.md): TUI usage

## Verified In This Checkout

The current refactored web runtime imports cleanly and the focused chat, room
policy, and health tests pass in the current tree.
