#!/bin/bash
# Start opsechat services and verify runtime health.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

START_TIMEOUT="${OPSECHAT_START_TIMEOUT:-90}"
POLL_INTERVAL="${OPSECHAT_POLL_INTERVAL:-3}"

wait_for_check() {
    local description="$1"
    local timeout_seconds="$2"
    local command_to_run="$3"
    local elapsed=0

    while [ "$elapsed" -lt "$timeout_seconds" ]; do
        if eval "$command_to_run" >/dev/null 2>&1; then
            echo "[OK] $description"
            return 0
        fi
        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done

    echo "[!] Timed out waiting for: $description"
    return 1
}

echo "[*] Using $COMPOSE_CMD_LABEL"
echo "[*] Starting opsechat services..."
compose up -d

echo ""
echo "[*] Waiting for containers to be reported by compose..."
wait_for_check "Tor container listed in compose ps" \
    "$START_TIMEOUT" \
    "compose ps | grep -q 'opsechat-tor'"
wait_for_check "Opsechat app container listed in compose ps" \
    "$START_TIMEOUT" \
    "compose ps | grep -q 'opsechat-app'"

echo ""
echo "[*] Running service-level health checks..."
wait_for_check "Tor control port is reachable (9051)" \
    "$START_TIMEOUT" \
    "compose exec -T tor nc -z localhost 9051"
wait_for_check "Opsechat /health endpoint responds" \
    "$START_TIMEOUT" \
    "compose exec -T opsechat curl --fail --silent http://127.0.0.1:5000/health"

echo ""
echo "[OK] Services are up and healthy"
echo ""
echo "[*] To view the onion address, run:"
echo "    $COMPOSE_CMD_DISPLAY -f $COMPOSE_FILE logs opsechat"
echo ""
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo ""
echo "[*] To view all logs in real-time, run:"
echo "    $COMPOSE_CMD_DISPLAY -f $COMPOSE_FILE logs -f"
echo ""
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo ""
