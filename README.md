# OpSecChat

**Closed-roster OpenPGP chat over Tor hidden services.**
Anonymous, ephemeral, signed, and encrypted to a small group that has
verified each other's fingerprints out of band.

- **Version:** `0.8.0-alpha`
- **License:** MIT (see [`LICENSE.md`](LICENSE.md))

---

## What this is

A small Flask web app that runs on a Tor hidden service. Two or more
people lock a room to a fixed roster of OpenPGP public keys. From that
point on, every message in that room is **signed by the sender** and
**encrypted to the full roster** in the user's browser. The server
validates the envelope (sender membership, recipient set, roster hash,
epoch) and stores ciphertext only. Messages auto-burn after three minutes.

There is no account system, no message history, no attachments, no media,
no email, no key escrow, and no warrant-friendly logging.

> ### What is _not_ in alpha
>
> Email, burner emails, HTTP mail, registrar/domain rotation, reviews, the
> legacy "drop chat" interface, the standalone TUI client, AWS
> CloudFormation, and Amazon Q integration are present in the repo but are
> **gated off by default and explicitly out of alpha scope**. See
> [`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md).

---

## Three ways to run it

| Persona            | One-liner                                            | Use it for                                  |
|--------------------|------------------------------------------------------|---------------------------------------------|
| Self-hosted ad-hoc | `python bin/chat-room.py --tor`                      | Ephemeral, just-for-this-conversation chat  |
| Hosted (compose)   | `./compose-up.sh`                                    | A long-running operator deployment          |
| Hosted (quadlets)  | `./install-quadlets.sh && systemctl --user start opsechat-app` | Production with systemd integration |

The full step-by-step for each persona is in [`QUICKSTART.md`](QUICKSTART.md).
The user-facing how-to (creating rooms, identities, fingerprint
verification, recovery) is in [`USER_DOCS.md`](USER_DOCS.md). Architecture
and contributor docs are in [`DEVELOPER_DOCS.md`](DEVELOPER_DOCS.md).

---

## Five-minute path (compose)

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
./compose-up.sh
curl http://127.0.0.1:8080/health
```

Find the onion URL once Tor publishes the descriptor:

```bash
docker compose -f container-compose.yml logs opsechat | grep -i onion
# (podman compose logs ... if you are on Podman)
```

Open the printed `<service>.onion` URL in Tor Browser and click
**Create New Chat Room**. Share the room URL with one other person and
walk through the in-room "Bootstrap Epoch 1" panel together.

When you are done:

```bash
./compose-down.sh
```

---

## Documentation map

- [`QUICKSTART.md`](QUICKSTART.md) -- shell-by-shell walkthrough of all three
  deployment modes. Every command in this file is exercised by an
  automated test, so the doc cannot quietly drift.
- [`USER_DOCS.md`](USER_DOCS.md) -- the user side: creating a room,
  generating or importing an identity, verifying fingerprints,
  bootstrapping the roster, sending messages, backing up your private key.
- [`DEVELOPER_DOCS.md`](DEVELOPER_DOCS.md) -- repo layout, app factory and
  gating flags, where the closed-roster logic lives, how to run all
  three test suites, how to add a new route or test.
- [`docs/ALPHA_SCOPE.md`](docs/ALPHA_SCOPE.md) -- the authoritative fence
  between alpha and beta. If a feature is documented above without being
  in this file, the doc is wrong.
- [`docs/SECURITY.md`](docs/SECURITY.md) -- security model and threat notes.

---

## Repository layout (relevant parts)

```
bin/                  # User-facing launchers (chat-room.py, runserver.py, ...)
src/python/           # Application code (Flask app factory + closed-roster logic)
src/web/              # Templates and static assets served by Flask
containers/           # Dockerfile, Tor config, admin-proxy Caddyfile
quadlets/             # systemd unit files for the Podman quadlet deployment
scripts/              # Helper shell scripts (compose-up/down, compose-e2e)
tests/                # Alpha test suite (alpha/) plus pytest
tests/legacy/         # Out-of-alpha specs, opt-in via playwright-legacy.config.js
docs/                 # Long-form documentation
```

The repo deliberately stays flat: each top-level directory has a single
clear job. See [`DEVELOPER_DOCS.md`](DEVELOPER_DOCS.md) for the full map.

---

## License

MIT. See [`LICENSE.md`](LICENSE.md).

Copyright Hyperion Gray LLC.
