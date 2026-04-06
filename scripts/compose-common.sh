#!/bin/bash
# Shared helpers for compose wrapper scripts.

set -o pipefail

SCRIPT_DIR=""
REPO_ROOT=""
COMPOSE_FILE=""
COMPOSE_NAME=""
COMPOSE_CMD=()

init_compose_context() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"

    if [ -f "$SCRIPT_DIR/../container-compose.yml" ]; then
        REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    else
        REPO_ROOT="$SCRIPT_DIR"
    fi

    COMPOSE_FILE="$REPO_ROOT/container-compose.yml"
}

detect_compose_command() {
    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_NAME="podman-compose"
        COMPOSE_CMD=(podman-compose)
        return 0
    fi

    if command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
        COMPOSE_NAME="podman compose"
        COMPOSE_CMD=(podman compose)
        return 0
    fi

    if command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_NAME="docker-compose"
        COMPOSE_CMD=(docker-compose)
        return 0
    fi

    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        COMPOSE_NAME="docker compose"
        COMPOSE_CMD=(docker compose)
        return 0
    fi

    return 1
}

require_compose_command() {
    if detect_compose_command; then
        return 0
    fi

    echo "[!] Error: no supported compose command found."
    echo "[!] Install podman-compose (preferred), podman compose, docker-compose, or docker compose."
    return 1
}

compose() {
    "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" "$@"
}
