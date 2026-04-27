# Installation

## Core Profile

The default runtime is the hardened `core` profile. It mounts the operator console and the simple text chat only.

1. Install dependencies with `./install.sh` or create a virtual environment and run `pip install -r requirements.txt`.
2. Start the app with `python runserver_refactored.py`.
3. Open the operator console at `http://localhost:5000/` and use `/chat` for the simple chat interface.

## Extended Services

The burner mail and HTTP mail stack are disabled by default. Enable them only for development or isolated operator use.

```bash
export OPSECHAT_ENABLE_EXTENDED_SERVICES=1
python runserver_refactored.py
```

You can also enable specific components individually:

```bash
export OPSECHAT_ENABLE_EMAIL_STACK=1
export OPSECHAT_ENABLE_HTTP_MAIL=1
python runserver_refactored.py
```

## Tor Policy

For serious-opsec deployments, require onion-service ingress and route outbound registrar or mail traffic through the Tor SOCKS proxy.

```bash
export OPSECHAT_REQUIRE_TOR=1
export OPSECHAT_FORCE_TOR_EGRESS=1
export TOR_CONTROL_HOST=127.0.0.1
export TOR_CONTROL_PORT=9051
export TOR_SOCKS_HOST=127.0.0.1
export TOR_SOCKS_PORT=9050
python runserver_refactored.py
```

Tor protects the transport path. It does not replace a real application-layer end-to-end protocol.

## Notes

- Set `OPSECHAT_SECRET_KEY` in persistent deployments so session keys survive restarts.
- The current public-safe baseline is text-only chat. The extended mail features still need additional hardening before a production-facing release.
