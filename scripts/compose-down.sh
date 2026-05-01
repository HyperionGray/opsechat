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

# Determine which compose tool is available
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    echo "[*] Using docker compose (plugin)"
elif command -v docker-compose &> /dev/null && docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    echo "[*] Using docker-compose"
elif command -v podman-compose &> /dev/null && podman-compose version &> /dev/null; then
    COMPOSE_CMD="podman-compose"
    echo "[*] Using podman-compose"
else
    echo "[!] Error: No working compose command found."
    exit 1
fi

echo "[*] Stopping opsechat services..."
$COMPOSE_CMD -f "$COMPOSE_FILE" down

echo ""
echo "[✓] All services stopped and removed"
echo ""
echo "[*] To remove volumes as well (WARNING: This deletes Tor data), run:"
echo "    $COMPOSE_CMD -f $COMPOSE_FILE down -v"
echo ""
