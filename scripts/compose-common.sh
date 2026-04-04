#!/bin/bash
# Shared helpers for compose-based scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../container-compose.yml" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    REPO_ROOT="$SCRIPT_DIR"
fi

COMPOSE_FILE="$REPO_ROOT/container-compose.yml"
COMPOSE_RUNTIME="auto"
COMPOSE_CMD=()
COMPOSE_DISPLAY=""

print_compose_help() {
    cat <<'EOF'
Compose runtime options:
  --runtime auto     Auto-detect runtime (default, prefers Podman)
  --runtime podman   Require a Podman compose runtime
  --runtime docker   Require a Docker compose runtime
EOF
}

set_compose_runtime() {
    local runtime="${1:-auto}"
    case "$runtime" in
        auto|podman|docker)
            COMPOSE_RUNTIME="$runtime"
            ;;
        *)
            echo "[!] Invalid runtime: $runtime" >&2
            print_compose_help >&2
            exit 1
            ;;
    esac
}

set_compose_cmd() {
    local runtime="$COMPOSE_RUNTIME"

    if [ "$runtime" = "auto" ] || [ "$runtime" = "podman" ]; then
        if command -v podman-compose >/dev/null 2>&1; then
            COMPOSE_CMD=(podman-compose)
            COMPOSE_DISPLAY="podman-compose"
            return 0
        fi
        if command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
            COMPOSE_CMD=(podman compose)
            COMPOSE_DISPLAY="podman compose"
            return 0
        fi
    fi

    if [ "$runtime" = "auto" ] || [ "$runtime" = "docker" ]; then
        if command -v docker-compose >/dev/null 2>&1; then
            COMPOSE_CMD=(docker-compose)
            COMPOSE_DISPLAY="docker-compose"
            return 0
        fi
        if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
            COMPOSE_CMD=(docker compose)
            COMPOSE_DISPLAY="docker compose"
            return 0
        fi
    fi

    if [ "$runtime" = "podman" ]; then
        echo "[!] Error: No Podman compose runtime found." >&2
        echo "[!] Install podman-compose or Podman with compose plugin support." >&2
    elif [ "$runtime" = "docker" ]; then
        echo "[!] Error: No Docker compose runtime found." >&2
        echo "[!] Install docker-compose or Docker with compose plugin support." >&2
    else
        echo "[!] Error: No compose runtime found." >&2
        echo "[!] Install one of: podman-compose, podman compose, docker-compose, docker compose." >&2
    fi
    exit 1
}

compose_exec() {
    "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" "$@"
}

services_appear_running() {
    local ps_output
    ps_output="$(compose_exec ps 2>/dev/null || true)"
    if [[ "$ps_output" == *"opsechat-tor"* && "$ps_output" == *"opsechat-app"* ]]; then
        return 0
    fi
    return 1
}
