#!/bin/bash
# Script to start opsechat services with podman-compose or docker-compose

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

echo "[*] Starting opsechat services..."
run_compose -f "$COMPOSE_FILE" up -d

echo ""
echo "[*] Services starting..."
echo "[*] Waiting for services to be ready..."
sleep 5

# Check if services are running
if run_compose -f "$COMPOSE_FILE" ps | grep -q "opsechat-tor"; then
    echo "[✓] Tor daemon is running"
else
    echo "[!] Tor daemon failed to start"
fi

if run_compose -f "$COMPOSE_FILE" ps | grep -q "opsechat-app"; then
    echo "[✓] Opsechat application is running"
else
    echo "[!] Opsechat application failed to start"
fi

echo ""
echo "[*] To view the onion address, run:"
echo "    $COMPOSE_CMD_DISPLAY -f $COMPOSE_FILE logs opsechat"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo ""
echo "[*] To view all logs in real-time, run:"
echo "    $COMPOSE_CMD_DISPLAY logs -f"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
