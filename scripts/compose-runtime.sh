#!/bin/bash
# Shared compose runtime detection for opsechat scripts.
#
# Exposes:
#   - detect_compose_cmd: detect and validate compose runtime
#   - run_compose: execute detected compose command with args
#   - COMPOSE_CMD_DISPLAY: human-readable compose command name

COMPOSE_CMD=()
COMPOSE_CMD_DISPLAY=""

_set_compose_cmd_from_string() {
    local value="$1"
    read -r -a COMPOSE_CMD <<< "$value"
    COMPOSE_CMD_DISPLAY="$value"
}

detect_compose_cmd() {
    if [ -n "${OPSECHAT_COMPOSE_CMD:-}" ]; then
        _set_compose_cmd_from_string "$OPSECHAT_COMPOSE_CMD"
        if "${COMPOSE_CMD[@]}" version &> /dev/null; then
            return 0
        fi
        echo "[!] Error: OPSECHAT_COMPOSE_CMD is set but not usable: $OPSECHAT_COMPOSE_CMD" >&2
        return 1
    fi

    # Podman is preferred over Docker.
    if command -v podman &> /dev/null && podman compose version &> /dev/null; then
        COMPOSE_CMD=(podman compose)
        COMPOSE_CMD_DISPLAY="podman compose"
        return 0
    fi

    if command -v podman-compose &> /dev/null; then
        COMPOSE_CMD=(podman-compose)
        COMPOSE_CMD_DISPLAY="podman-compose"
        return 0
    fi

    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        COMPOSE_CMD=(docker compose)
        COMPOSE_CMD_DISPLAY="docker compose"
        return 0
    fi

    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD=(docker-compose)
        COMPOSE_CMD_DISPLAY="docker-compose"
        return 0
    fi

    echo "[!] Error: No supported compose runtime found." >&2
    echo "[!] Install podman (preferred) or docker compose." >&2
    return 1
}

run_compose() {
    "${COMPOSE_CMD[@]}" "$@"
}
