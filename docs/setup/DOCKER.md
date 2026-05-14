# Container Runtime

This guide covers the current compose-based container flow.

The compose stack uses a dedicated `tor` container and keeps the localhost-only
admin proxy off the Tor control/SOCKS network. That reduces the blast radius for
the browser-facing container, but it is not a full Whonix-style gateway/workstation
split yet.

## What It Starts

- `tor` container
- `opsechat` app container
- `admin-proxy` bound to `127.0.0.1:8080`

Network layout:

- `tor` and `opsechat` share a private backend network for Tor control/SOCKS
- `admin-proxy` and `opsechat` share a separate localhost-only admin network
- `admin-proxy` does not join the Tor backend network

The compose file is [`container-compose.yml`](../../container-compose.yml).

## Quick Start

```bash
cd /path/to/opsechat
./compose-up.sh
```

The helper script auto-detects:

- `podman-compose`
- `docker-compose`
- `docker compose`

## Access Points

Local operator access:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/chat`

The app inside the container uses the current refactored runtime, so the
onion-service web paths are also `/` and `/chat`.

The localhost admin proxy is for local operator access only; the onion service
remains the primary anonymous ingress path.

## Find The Onion URL

```bash
docker compose -f container-compose.yml logs opsechat
```

Or use:

```bash
./verify-setup.sh
```

## Useful Commands

```bash
./compose-down.sh
docker compose -f container-compose.yml logs -f
docker compose -f container-compose.yml ps
```

If you use Podman or legacy docker-compose, the helper scripts select the right
command automatically.

## Direct Host-Port Debugging

If you temporarily uncomment the app port mapping in `container-compose.yml`,
the app will answer directly on:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/chat`
- `http://127.0.0.1:5000/health`

Use that only for local debugging.

## Troubleshooting

### No onion URL yet

- wait 10-30 seconds for Tor publication
- inspect logs with `./verify-setup.sh` or the compose logs command

### Admin proxy is up but chat is not

- check `docker compose -f container-compose.yml logs opsechat`
- confirm the app container can answer `GET /health`

### Compose command not found

Install one of:

- `podman-compose`
- `docker-compose`
- Docker with the `compose` plugin
