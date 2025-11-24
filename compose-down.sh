#!/bin/bash
# Script to stop opsechat services with podman-compose or docker-compose

set -e

# Determine which compose tool is available
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
    echo "[*] Using podman-compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    echo "[*] Using docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    echo "[*] Using docker compose (plugin)"
else
    echo "[!] Error: Neither podman-compose nor docker-compose found."
    exit 1
fi

echo "[*] Stopping opsechat services..."
$COMPOSE_CMD down

echo ""
echo "[✓] All services stopped and removed"
echo ""
echo "[*] To remove volumes as well (WARNING: This deletes Tor data), run:"
echo "    $COMPOSE_CMD down -v"
echo ""
