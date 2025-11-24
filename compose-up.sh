#!/bin/bash
# Script to start opsechat services with podman-compose or docker-compose

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
    echo "[!] Please install one of them:"
    echo "    - Podman: https://podman.io/getting-started/installation"
    echo "    - Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "[*] Starting opsechat services..."
$COMPOSE_CMD up -d

echo ""
echo "[*] Services starting..."
echo "[*] Waiting for services to be ready..."
sleep 5

# Check if services are running
if $COMPOSE_CMD ps | grep -q "opsechat-tor"; then
    echo "[✓] Tor daemon is running"
else
    echo "[!] Tor daemon failed to start"
fi

if $COMPOSE_CMD ps | grep -q "opsechat-app"; then
    echo "[✓] Opsechat application is running"
else
    echo "[!] Opsechat application failed to start"
fi

echo ""
echo "[*] To view the onion address, run:"
echo "    $COMPOSE_CMD logs opsechat"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo ""
echo "[*] To view all logs in real-time, run:"
echo "    $COMPOSE_CMD logs -f"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
