# Setup: Installation

The canonical installation guide is [../../INSTALL.md](../../INSTALL.md).

Use this file as a short pointer, not as a separate source of truth.

## Supported Paths

1. project-local `.venv`
2. compose stack via `./compose-up.sh`
3. Podman quadlets

## Not Supported Here

- legacy `install.sh` flow
- distro-specific instructions copied forward from older releases

## Current Runtime Paths

- operator console: `/`
- chat rooms: `/chat`
- health: `/health`

## Short Native Example

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python chat-room.py
```

## Short Container Example

```bash
./compose-up.sh
./verify-setup.sh
```
