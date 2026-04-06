#!/bin/bash
# Script to start opsechat services with podman-compose or docker-compose.

set -e

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/compose-common.sh"
init_compose_context
require_compose_command

echo "[*] Using $COMPOSE_NAME"
echo "[*] Starting opsechat services..."
compose up -d

echo ""
echo "[*] Services starting..."
echo "[*] Waiting for services to be ready..."
sleep 5

# Check if services are running
if compose ps | grep -q "opsechat-tor"; then
    echo "[✓] Tor daemon is running"
else
    echo "[!] Tor daemon failed to start"
fi

if compose ps | grep -q "opsechat-app"; then
    echo "[✓] Opsechat application is running"
else
    echo "[!] Opsechat application failed to start"
fi

echo ""
echo "[*] To view the onion address, run:"
echo "    $COMPOSE_NAME -f $COMPOSE_FILE logs opsechat"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./compose-doctor.sh"
echo "    # or: ./verify-setup.sh (legacy alias)"
echo ""
echo "[*] To view all logs in real-time, run:"
echo "    $COMPOSE_NAME -f $COMPOSE_FILE logs -f"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
