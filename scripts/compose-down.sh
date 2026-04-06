#!/bin/bash
# Script to stop opsechat services with podman-compose or docker-compose.

set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

detect_compose
echo "[*] Using $COMPOSE_NAME"
echo "[*] Stopping opsechat services..."
run_compose down

echo ""
echo "[*] All services stopped and removed."
echo ""
echo "[*] To remove volumes as well (WARNING: This deletes Tor data), run:"
echo "    $COMPOSE_CMD -f $COMPOSE_FILE down -v"
echo ""
