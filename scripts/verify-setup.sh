#!/bin/bash
# Verify compose-based opsechat deployment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/compose-common.sh"

RUNTIME_SELECTED="auto"

usage() {
    cat <<'EOF'
Usage: ./verify-setup.sh [options]

Options:
  --runtime {auto|podman|docker}  Choose runtime backend (default: auto)
  -h, --help                       Show this help text

Examples:
  ./verify-setup.sh
  ./verify-setup.sh --runtime podman
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --runtime)
            shift
            [ $# -gt 0 ] || { echo "[!] Missing value for --runtime" >&2; exit 1; }
            RUNTIME_SELECTED="$1"
            set_compose_runtime "$RUNTIME_SELECTED"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[!] Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

set_compose_cmd

echo "========================================"
echo "Opsechat Container Verification"
echo "========================================"
echo ""
echo "[*] Runtime: $COMPOSE_DISPLAY"
echo "[*] Compose file: $COMPOSE_FILE"
echo ""

echo "[*] Checking container status..."
ps_output="$(compose_exec ps 2>/dev/null || true)"
if [[ "$ps_output" == *"opsechat-tor"* ]]; then
    echo "[OK] Tor container is running"
else
    echo "[FAIL] Tor container is not running"
    echo "       Run: ./compose-up.sh --runtime $RUNTIME_SELECTED"
    exit 1
fi

if [[ "$ps_output" == *"opsechat-app"* ]]; then
    echo "[OK] Opsechat container is running"
else
    echo "[FAIL] Opsechat container is not running"
    echo "       Run: ./compose-up.sh --runtime $RUNTIME_SELECTED"
    exit 1
fi

echo ""
echo "[*] Checking Tor service health..."
if compose_exec exec -T tor nc -z localhost 9051 >/dev/null 2>&1; then
    echo "[OK] Tor control port is accessible (9051)"
else
    echo "[WARN] Tor control port is not accessible yet"
fi

if compose_exec exec -T tor nc -z localhost 9050 >/dev/null 2>&1; then
    echo "[OK] Tor SOCKS port is accessible (9050)"
else
    echo "[WARN] Tor SOCKS port is not accessible yet"
fi

echo ""
echo "[*] Checking for hidden service address..."
onion_addr="$(compose_exec logs opsechat 2>/dev/null | sed -nE 's/.*([a-z2-7]{16,56}\.onion\/[a-zA-Z0-9_-]{8,}).*/\1/p' | sed -n '1p')"
if [ -n "$onion_addr" ]; then
    echo "[OK] Hidden service is running"
    echo "========================================"
    echo "Service URL:"
    echo "$onion_addr"
    echo "========================================"
else
    echo "[WARN] Hidden service address not found in logs yet"
    echo "       This can take 1-2 minutes on first startup."
fi

echo ""
echo "[*] Checking container network..."
if compose_exec exec -T opsechat ping -c 1 tor >/dev/null 2>&1; then
    echo "[OK] Opsechat can reach Tor container"
else
    echo "[WARN] Network connectivity check failed (may be transient)"
fi

echo ""
echo "[*] Current service table:"
compose_exec ps

echo ""
echo "========================================"
echo "Verification complete"
echo "========================================"
echo "Useful commands:"
echo "  View logs:        $COMPOSE_DISPLAY -f $COMPOSE_FILE logs -f"
echo "  Restart services: ./compose-down.sh --runtime $RUNTIME_SELECTED && ./compose-up.sh --runtime $RUNTIME_SELECTED"
echo "  Stop services:    ./compose-down.sh --runtime $RUNTIME_SELECTED"
echo ""
