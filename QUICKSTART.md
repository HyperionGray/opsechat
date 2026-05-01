# Quick Start

This is the shortest path from clone to a running room.

## 1. Local Web Mode

```bash
cd /path/to/opsechat

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt -r requirements-dev.txt
python chat-room.py
```

Open:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/chat`

What to do next:

1. open `/chat`
2. create a room
3. generate or import your OpenPGP identity
4. add every member before locking the roster
5. use the room URL with your contacts

## 2. Tor Web Mode

Start a Tor daemon with a control port:

```bash
tor --ControlPort 9051 --CookieAuthentication 1
```

Then:

```bash
source .venv/bin/activate
python chat-room.py --tor
```

The launcher prints onion URLs for the operator console and the room UI.

## 3. Local Debug/Test Mode

Use this when you want a predictable local port for tests or route checks:

```bash
source .venv/bin/activate
python runserver_refactored.py test
```

Current debug URLs:

- `http://127.0.0.1:5001/`
- `http://127.0.0.1:5001/chat`
- `http://127.0.0.1:5001/health`

## 4. Container Mode

```bash
./compose-up.sh
```

Local operator access:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/chat`

To fetch the onion URL from logs:

```bash
docker compose -f container-compose.yml logs opsechat
```

Or use the helper:

```bash
./verify-setup.sh
```

## 5. TUI Mode

Server:

```bash
source .venv/bin/activate
python tui-server.py
```

Client:

```bash
source .venv/bin/activate
python tui-client.py
```

## Common Flags

`chat-room.py`:

- `--host 0.0.0.0`
- `--port 8080`
- `--tor`

## Current Defaults

- operator console: `/`
- room UI: `/chat`
- health: `/health`
- message expiry: 3 minutes
- DMs: 60 seconds
- storage: in-memory only
