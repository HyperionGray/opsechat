# OpSecChat Quickstart

Three personas. Each is a copy-pasteable sequence that gets you to a
working signed-and-encrypted chat exchange. Pick the one that matches
how you want to run the service.

> Every shell command in this file is exercised by an automated test:
>
> - Self-hosted ad-hoc and operator-console flows: `tests/alpha/*.spec.js`
>   driven against the real Flask app.
> - Compose stack: `scripts/test-compose-e2e.sh` brings the stack up,
>   runs the alpha specs against it, and tears it back down.
>
> If you change a command here and forget to update the matching test,
> the test will fail and you will know.

For an explanation of what is in scope vs. punted to beta, see
[`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md). For the user-side how-to
once a room is up, see [`USER_DOCS.md`](USER_DOCS.md).

---

## 1. Self-hosted ad-hoc (5 minutes)

You want a one-off room for one conversation. The fastest path is to run
the Flask app on your own machine. Optionally publish it as a Tor hidden
service so the other side never needs to be on the same network as you.

### 1.1 Install (one-time)

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1.2 Run locally (no Tor)

```bash
source .venv/bin/activate
python bin/chat-room.py
```

The app prints:

```
[local] OpSecChat server started
[console] Operator Console: http://127.0.0.1:5000/
[chat]    Chat Rooms:        http://127.0.0.1:5000/chat
```

Open <http://127.0.0.1:5000/chat> in two browser tabs (or two browsers).
One tab clicks **Create New Chat Room** and shares the resulting URL with
the other tab. From there, follow [`USER_DOCS.md`](USER_DOCS.md) -- it
walks you through generating identities, exchanging public keys, locking
the roster, and sending the first message.

### 1.3 Run as a Tor hidden service

You will need a local Tor daemon with a control port:

```bash
# In a separate terminal:
tor --ControlPort 9051 --CookieAuthentication 1
```

Then:

```bash
source .venv/bin/activate
python bin/chat-room.py --tor
```

The app prints:

```
[tor] OpSecChat hidden service created
[console] Operator Console: http://<...>.onion/
[chat]    Chat Rooms:        http://<...>.onion/chat
```

Open the `<...>.onion/chat` URL in Tor Browser, click **Create New Chat
Room**, and share the resulting URL with the other person via your
preferred out-of-band channel.

### 1.4 Stop

`Ctrl+C` in the terminal running `bin/chat-room.py`. Hidden services are
ephemeral; tearing the process down also removes the onion address.

---

## 2. Hosted operator (compose, 10 minutes)

You want a long-running deployment so people can join you on a stable
onion. Use the compose stack: it brings up a Tor container, the OpSecChat
app, and a localhost-only admin proxy.

### 2.1 Bring the stack up

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
./compose-up.sh
```

The script auto-detects `podman-compose`, `docker compose`, or
`docker-compose`. Containers come up in dependency order:

1. `opsechat-tor` -- the Tor daemon
2. `opsechat-app` -- the Flask app (binds port `5000` inside its network)
3. `opsechat-admin-proxy` -- a Caddy proxy on **127.0.0.1:8087** for the
   operator. The Tor onion is the public surface; the admin proxy is
   never exposed off-host.

### 2.2 Verify health

```bash
curl http://127.0.0.1:8087/health
# {"active_rooms":0,"checks":{...},"status":"healthy",...,"version":"0.8.0-alpha"}
```

### 2.3 Find the onion address

Tor publication takes 60-120 seconds after first start. Once the descriptor
is live:

```bash
# docker compose:
docker compose -f container-compose.yml logs opsechat | grep -i onion
# podman compose:
podman compose -f container-compose.yml logs opsechat | grep -i onion
```

Look for a line like:

```
[*] Started a new hidden service with the address of <abc123...>.onion
```

### 2.4 Use it

Operator: open <http://127.0.0.1:8087/> for the operator console.
Users: share `http://<abc123...>.onion/chat` over an out-of-band channel
and follow [`USER_DOCS.md`](USER_DOCS.md).

### 2.5 Tear the stack down

```bash
./compose-down.sh
```

### 2.6 Container-up-to-container-down test

To prove the entire deployment works end-to-end, run:

```bash
./scripts/test-compose-e2e.sh
```

This script brings the stack up, polls `/health` until green, runs the
alpha Playwright suite against `127.0.0.1:8087`, and brings the stack
back down (in a `trap` so it tears down even on failure). Use this as
your acceptance test before announcing a deployment.

---

## 3. Hosted operator (quadlets, 15 minutes)

Same end state as the compose stack, but the units are managed by
systemd. Recommended for production hosts where you want native systemd
logging, restart policies, and boot ordering.

### 3.1 Install

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
podman build -t localhost/opsechat:latest .
./install-quadlets.sh
```

### 3.2 Start

```bash
systemctl --user start opsechat-app
```

### 3.3 Find the onion address

```bash
journalctl --user -u opsechat-app -f | grep -i onion
```

(Or omit `-f` and just grep historical journal output.)

### 3.4 Manage

```bash
# Status
systemctl --user status opsechat-app
# Stop
systemctl --user stop opsechat-app
# Restart
systemctl --user restart opsechat-app
```

To enable boot-time start without an interactive login, enable lingering
once: `sudo loginctl enable-linger $USER`.

See [`quadlets/README.md`](quadlets/README.md) for the full quadlet
reference.

---

## 4. Test mode for developers

If you are iterating on the code and just want the app on `127.0.0.1`
with no Tor:

```bash
source .venv/bin/activate
python bin/runserver.py test
```

This binds <http://127.0.0.1:5001> and skips the Tor publication
entirely. The Playwright `webServer` block uses this same flow on
port `5111`.

For the full developer workflow including running all three test
suites, see [`DEVELOPER_DOCS.md`](DEVELOPER_DOCS.md).

---

## What can go wrong (the short list)

| Symptom                                     | Likely cause and fix                                                                                            |
|---------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| `compose-up.sh: command not found`          | You did not `cd` into the repo. Or you are on Windows; this stack is Linux/macOS only.                          |
| `[!] Error: No working compose command found` | Install `podman-compose`, `docker-compose`, or the `docker compose` plugin. Podman is preferred (`podman --version`). |
| `/health` never goes green                  | Inspect `docker compose -f container-compose.yml logs opsechat`. The most common cause is a stale image; rebuild with `./compose-up.sh` (it builds on every up). |
| `Tor proxy or Control Port are not running` | For ad-hoc: ensure `tor --ControlPort 9051 --CookieAuthentication 1` is running. For compose: it is built in.   |
| Browser shows "Room not found or expired"   | Rooms expire after one hour of inactivity. Ask the other side to create a new room and share the URL again.     |
| Sending message says "Bootstrap the room roster..." | You skipped the bootstrap step. See `USER_DOCS.md` -> "Locking the roster (epoch 1)".                  |

---

## Next steps

- Read [`USER_DOCS.md`](USER_DOCS.md) before sharing a room URL with anyone.
- Read [`docs/SECURITY.md`](docs/SECURITY.md) before deploying publicly.
- Read [`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md) to understand exactly
  what alpha promises and what it does not.
