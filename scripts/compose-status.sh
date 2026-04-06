#!/bin/bash
# Script to inspect opsechat compose deployment health/status.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

init_compose_context "$SCRIPT_DIR"
require_compose_file
show_compose_selection

echo "[*] Compose file: $COMPOSE_FILE"
echo ""

echo "[*] Service status:"
compose ps
echo ""

check_container() {
    local container_name="$1"
    local display_name="$2"
    local expected_health="$3"
    local health

    if container_running "$container_name"; then
        echo "[✓] $display_name is running"
    else
        echo "[!] $display_name is not running"
        return 1
    fi

    health="$(container_health "$container_name")"
    if [ "$expected_health" = "healthy" ]; then
        if [ "$health" = "healthy" ]; then
            echo "[✓] $display_name health is healthy"
        else
            echo "[!] $display_name health is $health (expected healthy)"
            return 1
        fi
    else
        echo "[*] $display_name health is $health"
    fi
}

status_ok=0

echo "[*] Container checks:"
if ! check_container "opsechat-tor" "Tor daemon" "healthy"; then
    status_ok=1
fi

if ! check_container "opsechat-app" "Opsechat app" "healthy"; then
    status_ok=1
fi

echo ""
onion_address="$(extract_onion_address || true)"
if [ -n "$onion_address" ]; then
    echo "[✓] Hidden service address detected: $onion_address"
else
    echo "[*] Hidden service address not found in logs yet"
fi

echo ""
echo "[*] Useful commands:"
echo "    ./compose-up.sh"
echo "    ./compose-down.sh"
echo "    ./verify-setup.sh"
echo "    ${COMPOSE_CMD[*]} -f $COMPOSE_FILE logs -f"

if [ "$status_ok" -ne 0 ]; then
    exit "$status_ok"
fi
