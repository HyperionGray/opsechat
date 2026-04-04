#!/bin/bash
# Script to stop opsechat services with podman-compose or docker-compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../container-compose.yml" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    REPO_ROOT="$SCRIPT_DIR"
fi
COMPOSE_FILE="$REPO_ROOT/container-compose.yml"
COMPOSE_LIB="$REPO_ROOT/scripts/compose-runtime.sh"

if [ ! -f "$COMPOSE_LIB" ]; then
    echo "[!] Error: compose runtime helper not found at $COMPOSE_LIB"
    exit 1
fi

source "$COMPOSE_LIB"
detect_compose_cmd
echo "[*] Using $COMPOSE_CMD_DISPLAY"

echo "[*] Stopping opsechat services..."
run_compose -f "$COMPOSE_FILE" down

echo ""
echo "[✓] All services stopped and removed"
echo ""
echo "[*] To remove volumes as well (WARNING: This deletes Tor data), run:"
echo "    $COMPOSE_CMD_DISPLAY -f $COMPOSE_FILE down -v"
echo ""
