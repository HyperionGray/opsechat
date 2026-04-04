#!/bin/bash
# Shared compose helpers for opsechat scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/container-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "[!] Error: compose file not found at $COMPOSE_FILE"
    exit 1
fi

if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_BIN=(podman-compose)
    COMPOSE_CMD_LABEL="podman-compose"
    COMPOSE_CMD_DISPLAY="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN=(docker-compose)
    COMPOSE_CMD_LABEL="docker-compose"
    COMPOSE_CMD_DISPLAY="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN=(docker compose)
    COMPOSE_CMD_LABEL="docker compose plugin"
    COMPOSE_CMD_DISPLAY="docker compose"
else
    echo "[!] Error: Neither podman-compose, docker-compose, nor docker compose plugin is available."
    exit 1
fi

compose() {
    "${COMPOSE_BIN[@]}" -f "$COMPOSE_FILE" "$@"
}
