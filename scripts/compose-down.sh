#!/usr/bin/env bash
# Script to stop opsechat services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/compose-common.sh
source "$SCRIPT_DIR/compose-common.sh"

setup_compose_paths "$SCRIPT_DIR"
detect_compose_runtime

echo "[*] Using ${COMPOSE_LABEL}"
echo "[*] Stopping opsechat services..."
run_compose down

echo
echo "[+] All services stopped and removed"
echo
echo "[*] To remove volumes as well (WARNING: This deletes Tor data), run:"
echo "    ${COMPOSE_CMD[*]} -f ${COMPOSE_FILE} down -v"
echo
