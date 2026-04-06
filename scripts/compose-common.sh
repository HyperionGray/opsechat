#!/bin/bash
# Shared helpers for compose scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../container-compose.yml" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    REPO_ROOT="$SCRIPT_DIR"
fi
COMPOSE_FILE="$REPO_ROOT/container-compose.yml"

detect_compose() {
    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"
        COMPOSE_NAME="podman-compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
        COMPOSE_NAME="docker-compose"
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        COMPOSE_NAME="docker compose"
    else
        echo "[!] Error: Neither podman-compose nor docker-compose found."
        echo "[!] Please install one of them:"
        echo "    - Podman: https://podman.io/getting-started/installation"
        echo "    - Docker: https://docs.docker.com/get-docker/"
        return 1
    fi
}

run_compose() {
    $COMPOSE_CMD -f "$COMPOSE_FILE" "$@"
}

is_service_present_in_ps() {
    local service_name="$1"
    run_compose ps | grep -q "$service_name"
}
