#!/bin/bash
# Script to start opsechat services with podman-compose or docker-compose

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../container-compose.yml" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    REPO_ROOT="$SCRIPT_DIR"
fi
COMPOSE_FILE="$REPO_ROOT/container-compose.yml"

# Determine which compose tool is available.
if command -v podman-compose > /dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
    CONTAINER_ENGINE="podman"
    echo "[*] Using podman-compose"
elif command -v docker-compose > /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    CONTAINER_ENGINE="docker"
    echo "[*] Using docker-compose"
elif command -v docker > /dev/null 2>&1 && docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    CONTAINER_ENGINE="docker"
    echo "[*] Using docker compose (plugin)"
else
    echo "[!] Error: Neither podman-compose nor docker-compose found."
    echo "[!] Please install one of them:"
    echo "    - Podman: https://podman.io/getting-started/installation"
    echo "    - Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

get_container_state() {
    "$CONTAINER_ENGINE" inspect --format '{{.State.Status}}' "$1" 2>/dev/null || echo "missing"
}

get_container_health() {
    "$CONTAINER_ENGINE" inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1" 2>/dev/null || echo "unknown"
}

print_failure_diagnostics() {
    echo ""
    echo "[!] Container startup diagnostics:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps || true
    echo ""
    echo "[!] Recent service logs:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs tor opsechat || true
}

TIMEOUT_SECONDS="${OPSECHAT_STARTUP_TIMEOUT:-120}"
POLL_SECONDS=3

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || [ "$TIMEOUT_SECONDS" -lt 1 ]; then
    echo "[!] Error: OPSECHAT_STARTUP_TIMEOUT must be a positive integer."
    exit 1
fi

echo "[*] Starting opsechat services..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d

echo ""
echo "[*] Waiting for services to report ready state..."
echo "[*] Timeout: ${TIMEOUT_SECONDS}s (override with OPSECHAT_STARTUP_TIMEOUT)"

DEADLINE=$(( $(date +%s) + TIMEOUT_SECONDS ))
while true; do
    TOR_STATE="$(get_container_state "opsechat-tor")"
    TOR_HEALTH="$(get_container_health "opsechat-tor")"
    APP_STATE="$(get_container_state "opsechat-app")"
    APP_HEALTH="$(get_container_health "opsechat-app")"

    echo "[*] tor(state=$TOR_STATE, health=$TOR_HEALTH) app(state=$APP_STATE, health=$APP_HEALTH)"

    TOR_READY=0
    APP_READY=0
    if [ "$TOR_STATE" = "running" ] && { [ "$TOR_HEALTH" = "healthy" ] || [ "$TOR_HEALTH" = "none" ]; }; then
        TOR_READY=1
    fi
    if [ "$APP_STATE" = "running" ] && { [ "$APP_HEALTH" = "healthy" ] || [ "$APP_HEALTH" = "none" ]; }; then
        APP_READY=1
    fi

    if [ "$TOR_READY" -eq 1 ] && [ "$APP_READY" -eq 1 ]; then
        echo "[OK] Tor daemon is ready"
        echo "[OK] Opsechat application is ready"
        break
    fi

    if [ "$TOR_HEALTH" = "unhealthy" ] || [ "$APP_HEALTH" = "unhealthy" ]; then
        echo "[!] A container became unhealthy during startup."
        print_failure_diagnostics
        exit 1
    fi

    if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        echo "[!] Timed out waiting for services to become ready."
        print_failure_diagnostics
        exit 1
    fi

    sleep "$POLL_SECONDS"
done

echo ""
echo "[*] To view the onion address, run:"
echo "    $COMPOSE_CMD -f \"$COMPOSE_FILE\" logs opsechat"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo ""
echo "[*] To view all logs in real-time, run:"
echo "    $COMPOSE_CMD -f \"$COMPOSE_FILE\" logs -f"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
