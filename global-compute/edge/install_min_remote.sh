#!/usr/bin/env bash
# scripts/edge/install_min_remote.sh
# Install the minimal PacketFS quadlet remotely via SSH without a registry.
# Usage: scripts/edge/install_min_remote.sh user@host
set -euo pipefail
HOST=${1:?"usage: $0 user@host"}
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_IMG="/tmp/packetfs-min.tar"
IMG="localhost/packetfs-min:latest"

# Build image locally if missing
if ! podman image exists "$IMG"; then
  "$ROOT_DIR/scripts/container/build_min.sh"
fi

# Save and copy image
podman save "$IMG" -o "$ROOT_DIR$TMP_IMG"
sudo -n true 2>/dev/null || true
scp -q "$ROOT_DIR$TMP_IMG" "$HOST:$TMP_IMG"
rm -f "$ROOT_DIR$TMP_IMG"

# Template quadlet on the fly on remote (user scope by default)
QUAD_SRC="$ROOT_DIR/deploy/quadlet/packetfs-min.container.in"
QUAD_TMP="/tmp/packetfs-min.container"
REPO_ESC="$(printf '%s' "$ROOT_DIR" | sed 's/[&/]/\\&/g')"
sed "s#__REPO_ROOT__#${REPO_ESC}#g" "$QUAD_SRC" > "$ROOT_DIR$QUAD_TMP"
scp -q "$ROOT_DIR$QUAD_TMP" "$HOST:$QUAD_TMP"
rm -f "$ROOT_DIR$QUAD_TMP"

# Remote install: load image, place quadlet, reload, start
ssh -q "$HOST" bash -lc "'\nset -euo pipefail\nif command -v podman >/dev/null 2>&1; then true; else echo podman missing >&2; exit 1; fi\nif [[ \"$(id -u)\" -eq 0 ]]; then DEST=/etc/containers/systemd; SCOPE=system; else DEST=\"$HOME/.config/containers/systemd\"; SCOPE=user; fi\nmkdir -p \"$DEST\"\npodman load -i \"$TMP_IMG\"\nmv -f \"$QUAD_TMP\" \"$DEST/packetfs-min.container\"\nsystemctl --$SCOPE daemon-reload\nsystemctl --$SCOPE enable --now container-packetfs-min.service\n'"

printf "Remote install done: %s\n" "$HOST"
