#!/bin/bash
# Script to stop opsechat services with podman-compose or docker-compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"
init_compose_context "$SCRIPT_DIR"
require_compose_file
show_compose_selection

echo "[*] Stopping opsechat services..."
compose down

echo ""
echo "[✓] All services stopped and removed"
echo ""
echo "[*] To remove volumes as well (WARNING: This deletes Tor data), run:"
echo "    $COMPOSE_TOOL_NAME -f $COMPOSE_FILE down -v"
echo ""
