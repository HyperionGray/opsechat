#!/bin/bash
# Script to start opsechat services with podman-compose or docker-compose.

set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

WAIT_TIMEOUT=60
SKIP_WAIT=0

is_positive_integer() {
    [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -gt 0 ]]
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            echo "Usage: ./compose-up.sh [--wait-timeout <seconds>] [--no-wait]"
            exit 0
            ;;
        --wait-timeout)
            if [[ $# -lt 2 ]]; then
                echo "[!] Error: --wait-timeout requires a value in seconds."
                exit 1
            fi
            WAIT_TIMEOUT="$2"
            if ! is_positive_integer "$WAIT_TIMEOUT"; then
                echo "[!] Error: --wait-timeout must be a positive integer."
                exit 1
            fi
            shift 2
            ;;
        --no-wait)
            SKIP_WAIT=1
            shift
            ;;
        *)
            echo "[!] Unknown option: $1"
            echo "Usage: ./compose-up.sh [--wait-timeout <seconds>] [--no-wait]"
            exit 1
            ;;
    esac
done

detect_compose
echo "[*] Using $COMPOSE_NAME"
echo "[*] Starting opsechat services..."
run_compose up -d

echo ""
if [[ "$SKIP_WAIT" -eq 0 ]]; then
    echo "[*] Waiting up to ${WAIT_TIMEOUT}s for service health..."
    "$SCRIPT_DIR/compose-status.sh" --wait --timeout "$WAIT_TIMEOUT"
else
    echo "[*] Skipping health wait (--no-wait)."
    "$SCRIPT_DIR/compose-status.sh"
fi

echo ""
echo "[*] To view the onion address, run:"
echo "    $COMPOSE_CMD -f $COMPOSE_FILE logs opsechat"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
