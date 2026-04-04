#!/bin/bash
# Stop opsechat services with the detected compose tool.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

echo "[*] Using $COMPOSE_CMD_LABEL"
echo "[*] Stopping opsechat services..."
compose down

echo ""
echo "[OK] All services stopped and removed"
echo ""
echo "[*] To remove volumes as well (WARNING: This deletes Tor data), run:"
echo "    $COMPOSE_CMD_DISPLAY -f $COMPOSE_FILE down -v"
echo ""
