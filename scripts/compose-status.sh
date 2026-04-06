#!/bin/bash
# Show compose service status and optional health wait.

set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

WAIT_FOR_HEALTH=0
TIMEOUT_SECONDS=60

usage() {
    echo "Usage: ./compose-status.sh [--wait] [--timeout <seconds>]"
}

validate_positive_integer() {
    local value="$1"
    [[ "$value" =~ ^[0-9]+$ ]] && [[ "$value" -gt 0 ]]
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wait)
            WAIT_FOR_HEALTH=1
            shift
            ;;
        --timeout)
            if [[ $# -lt 2 ]]; then
                echo "[!] Error: --timeout requires a value in seconds."
                usage
                exit 1
            fi
            TIMEOUT_SECONDS="$2"
            if ! validate_positive_integer "$TIMEOUT_SECONDS"; then
                echo "[!] Error: timeout must be a positive integer."
                exit 1
            fi
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[!] Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

detect_compose
echo "[*] Using $COMPOSE_NAME"
echo "[*] Compose file: $COMPOSE_FILE"

run_compose ps

echo ""
if is_service_present_in_ps "opsechat-tor"; then
    echo "[✓] Tor service appears in compose status"
else
    echo "[!] Tor service is not running"
fi

if is_service_present_in_ps "opsechat-app"; then
    echo "[✓] Opsechat service appears in compose status"
else
    echo "[!] Opsechat service is not running"
fi

if [[ "$WAIT_FOR_HEALTH" -eq 1 ]]; then
    echo ""
    echo "[*] Waiting for Tor control port and app health (timeout: ${TIMEOUT_SECONDS}s)..."
    deadline=$((SECONDS + TIMEOUT_SECONDS))
    tor_ready=0
    app_ready=0

    while [[ $SECONDS -lt $deadline ]]; do
        if run_compose exec -T tor nc -z localhost 9051 >/dev/null 2>&1; then
            tor_ready=1
        fi

        if run_compose exec -T opsechat curl --fail --silent http://127.0.0.1:5000/health >/dev/null 2>&1; then
            app_ready=1
        fi

        if [[ "$tor_ready" -eq 1 && "$app_ready" -eq 1 ]]; then
            break
        fi

        sleep 2
    done

    if [[ "$tor_ready" -eq 1 ]]; then
        echo "[✓] Tor control port is reachable"
    else
        echo "[!] Tor control port did not become reachable within timeout"
    fi

    if [[ "$app_ready" -eq 1 ]]; then
        echo "[✓] Opsechat /health endpoint is reachable"
    else
        echo "[!] Opsechat /health endpoint did not become reachable within timeout"
    fi

    if [[ "$tor_ready" -eq 0 || "$app_ready" -eq 0 ]]; then
        echo "[!] Services did not become healthy in time."
        exit 1
    fi
fi

echo ""
echo "[*] Next commands:"
echo "    ./verify-setup.sh"
echo "    $COMPOSE_CMD -f $COMPOSE_FILE logs -f"
