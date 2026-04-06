#!/bin/bash
# Shared helpers for compose utility scripts.

set -o pipefail

init_compose_context() {
    local script_dir="$1"

    if [ -f "$script_dir/../container-compose.yml" ]; then
        REPO_ROOT="$(cd "$script_dir/.." && pwd)"
    else
        REPO_ROOT="$script_dir"
    fi

    COMPOSE_FILE="$REPO_ROOT/container-compose.yml"

    detect_compose_tool
}

detect_compose_tool() {
    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD=(podman-compose)
        COMPOSE_TOOL_NAME="podman-compose"
        CONTAINER_RUNTIME="podman"
    elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
        COMPOSE_CMD=(podman compose)
        COMPOSE_TOOL_NAME="podman compose"
        CONTAINER_RUNTIME="podman"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=(docker-compose)
        COMPOSE_TOOL_NAME="docker-compose"
        CONTAINER_RUNTIME="docker"
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD=(docker compose)
        COMPOSE_TOOL_NAME="docker compose"
        CONTAINER_RUNTIME="docker"
    else
        echo "[!] Error: No compose tool found."
        echo "[!] Install one of: podman-compose, podman compose plugin, docker-compose, docker compose plugin."
        return 1
    fi
}

require_compose_file() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo "[!] Missing compose file: $COMPOSE_FILE"
        return 1
    fi
}

show_compose_selection() {
    echo "[*] Using $COMPOSE_TOOL_NAME"
}

compose() {
    "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" "$@"
}

container_running() {
    local container_name="$1"
    local running

    running="$("$CONTAINER_RUNTIME" inspect --format '{{.State.Running}}' "$container_name" 2>/dev/null || true)"
    [ "$running" = "true" ]
}

container_health() {
    local container_name="$1"
    local health

    health="$("$CONTAINER_RUNTIME" inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_name" 2>/dev/null || true)"
    if [ -z "$health" ]; then
        health="unknown"
    fi
    printf '%s\n' "$health"
}

extract_onion_address() {
    compose logs --no-color opsechat 2>/dev/null \
        | grep -Eo "[a-z2-7]{16,56}\.onion/[a-zA-Z0-9_-]{8,}" \
        | head -n 1
}

