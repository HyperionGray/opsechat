#!/bin/bash
# Script to show opsechat compose service status and health

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../container-compose.yml" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    REPO_ROOT="$SCRIPT_DIR"
fi
COMPOSE_FILE="$REPO_ROOT/container-compose.yml"
DETAILED=0

if [ "$1" = "--detailed" ]; then
    DETAILED=1
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
    exit 1
fi

echo "[*] Service status"
PS_OUTPUT="$($COMPOSE_CMD -f "$COMPOSE_FILE" ps)"
echo "$PS_OUTPUT"
echo ""

STATUS=0

if echo "$PS_OUTPUT" | grep -q "opsechat-tor"; then
    echo "[✓] Tor service listed"
else
    echo "[!] Tor service missing from compose status"
    STATUS=1
fi

if echo "$PS_OUTPUT" | grep -q "opsechat-app"; then
    echo "[✓] Opsechat service listed"
else
    echo "[!] Opsechat service missing from compose status"
    STATUS=1
fi
echo ""

echo "[*] App health endpoint check"
if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T opsechat curl --fail --silent http://127.0.0.1:5000/health > /dev/null 2>&1; then
    echo "[✓] Opsechat /health endpoint reachable"
else
    echo "[!] Opsechat /health endpoint not reachable"
    STATUS=1
fi
echo ""

echo "[*] Tor control port check"
if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T tor nc -z localhost 9051 > /dev/null 2>&1; then
    echo "[✓] Tor control port reachable"
else
    echo "[!] Tor control port not reachable"
    STATUS=1
fi
echo ""

echo "[*] Quick commands"
echo "    View logs: $COMPOSE_CMD -f $COMPOSE_FILE logs -f"
echo "    Verify setup: ./verify-setup.sh"
echo "    Stop services: ./compose-down.sh"

if [ "$DETAILED" = "1" ]; then
    echo ""
    echo "[*] Last 20 log lines (opsechat)"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs --tail=20 opsechat || true
fi

exit "$STATUS"
