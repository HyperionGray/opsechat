#!/bin/bash
# Start opsechat services and wait for readiness.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

init_compose_context "$SCRIPT_DIR"
require_compose_file
show_compose_selection

STARTUP_TIMEOUT="${COMPOSE_STARTUP_TIMEOUT:-120}"
POLL_INTERVAL="${COMPOSE_STARTUP_POLL_INTERVAL:-3}"

echo "[*] Starting opsechat services..."
compose up -d --build

echo ""
echo "[*] Waiting for services to become ready..."

elapsed=0
while [ "$elapsed" -lt "$STARTUP_TIMEOUT" ]; do
    tor_running=false
    app_running=false
    tor_health="unknown"
    app_health="unknown"

    if container_running "opsechat-tor"; then
        tor_running=true
        tor_health="$(container_health "opsechat-tor")"
    fi

    if container_running "opsechat-app"; then
        app_running=true
        app_health="$(container_health "opsechat-app")"
    fi

    if [ "$tor_running" = true ] && [ "$app_running" = true ]; then
        tor_ok=false
        app_ok=false

        [ "$tor_health" = "healthy" ] || [ "$tor_health" = "none" ] && tor_ok=true
        [ "$app_health" = "healthy" ] || [ "$app_health" = "none" ] && app_ok=true

        if [ "$tor_ok" = true ] && [ "$app_ok" = true ]; then
            echo "[✓] Tor daemon is running (health: $tor_health)"
            echo "[✓] Opsechat application is running (health: $app_health)"
            break
        fi
    fi

    if [ "$tor_health" = "unhealthy" ] || [ "$app_health" = "unhealthy" ]; then
        echo "[!] Service reported unhealthy state (tor: $tor_health, opsechat: $app_health)"
        compose ps
        exit 1
    fi

    echo "[*] Current status after ${elapsed}s: tor running=$tor_running health=$tor_health; opsechat running=$app_running health=$app_health"
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
done

if [ "$elapsed" -ge "$STARTUP_TIMEOUT" ]; then
    echo "[!] Timed out waiting for services to become ready (${STARTUP_TIMEOUT}s)"
    compose ps
    echo ""
    echo "[*] Recent logs (tor/opsechat):"
    compose logs --no-color --tail 40 tor opsechat || true
    exit 1
fi

echo ""
echo "[*] To view the onion address, run:"
echo "    ${COMPOSE_CMD[*]} -f $COMPOSE_FILE logs opsechat"
echo ""
echo "[*] To inspect current status, run:"
echo "    ./compose-status.sh"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo ""
echo "[*] To view all logs in real-time, run:"
echo "    ${COMPOSE_CMD[*]} -f $COMPOSE_FILE logs -f"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
