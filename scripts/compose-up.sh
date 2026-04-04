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
WAIT_FOR_HEALTH=false

if [ "${1:-}" = "--wait" ] || [ "${1:-}" = "-w" ]; then
    WAIT_FOR_HEALTH=true
fi

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
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d

echo ""
echo "[*] Services starting..."
echo "[*] Waiting for services to be ready..."
sleep 5

# Check if services are running
if $COMPOSE_CMD -f "$COMPOSE_FILE" ps | grep -q "opsechat-tor"; then
    echo "[✓] Tor daemon is running"
else
    echo "[!] Tor daemon failed to start"
fi

if $COMPOSE_CMD -f "$COMPOSE_FILE" ps | grep -q "opsechat-app"; then
    echo "[✓] Opsechat application is running"
else
    echo "[!] Opsechat application failed to start"
fi

if [ "$WAIT_FOR_HEALTH" = true ]; then
    echo ""
    echo "[*] Waiting for opsechat health endpoint to report healthy..."
    max_attempts=30
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T opsechat curl --fail --silent http://127.0.0.1:5000/health >/dev/null 2>&1; then
            echo "[✓] Opsechat health endpoint is ready"
            break
        fi
        echo "[*] Health not ready yet (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    if [ $attempt -gt $max_attempts ]; then
        echo "[!] Timed out waiting for opsechat health endpoint"
        echo "    Check logs: $COMPOSE_CMD -f $COMPOSE_FILE logs opsechat"
        exit 1
    fi
fi

echo ""
echo "[*] To view the onion address, run:"
echo "    $COMPOSE_CMD -f $COMPOSE_FILE logs opsechat"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo ""
echo "[*] To start and block until /health is ready, run:"
echo "    ./compose-up.sh --wait"
echo ""
echo "[*] To view all logs in real-time, run:"
echo "    $COMPOSE_CMD logs -f"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
