#!/bin/bash
# Start opsechat services with a selected compose runtime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

DO_BUILD=0
DO_REBUILD=0
FOLLOW_LOGS=0
STATUS_ONLY=0
NO_WAIT=0
WAIT_TIMEOUT=60

print_help() {
    cat <<EOF
Usage: ./compose-up.sh [options]

Options:
  --runtime <auto|podman|docker>  Compose runtime selection (default: auto)
  --build                          Build images before starting
  --rebuild                        Recreate stack from scratch (down + up --build)
  --status                         Show service status and exit
  --follow                         Follow opsechat logs after startup
  --wait-timeout <seconds>         Wait timeout for startup checks (default: 60)
  --no-wait                        Skip startup wait checks
  -h, --help                       Show this help

Examples:
  ./compose-up.sh
  ./compose-up.sh --runtime podman --build
  ./compose-up.sh --rebuild --follow
EOF
    print_compose_help
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --runtime)
            shift
            if [[ $# -eq 0 ]]; then
                echo "[!] Missing value for --runtime" >&2
                exit 1
            fi
            set_compose_runtime "$1"
            shift
            ;;
        --build)
            DO_BUILD=1
            shift
            ;;
        --rebuild)
            DO_REBUILD=1
            DO_BUILD=1
            shift
            ;;
        --follow)
            FOLLOW_LOGS=1
            shift
            ;;
        --status)
            STATUS_ONLY=1
            shift
            ;;
        --wait-timeout)
            shift
            if [[ $# -eq 0 ]]; then
                echo "[!] Missing value for --wait-timeout" >&2
                exit 1
            fi
            WAIT_TIMEOUT="$1"
            shift
            ;;
        --no-wait)
            NO_WAIT=1
            shift
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            echo "[!] Unknown option: $1" >&2
            print_help >&2
            exit 1
            ;;
    esac
done

set_compose_cmd
echo "[*] Using $COMPOSE_DISPLAY"
echo "[*] Compose file: $COMPOSE_FILE"

if [[ "$STATUS_ONLY" -eq 1 ]]; then
    compose_exec ps
    exit 0
fi

if [[ "$DO_REBUILD" -eq 1 ]]; then
    echo "[*] Rebuilding stack: stopping existing services first..."
    compose_exec down --remove-orphans || true
fi

UP_ARGS=(up -d)
if [[ "$DO_BUILD" -eq 1 ]]; then
    UP_ARGS+=(--build)
fi

echo "[*] Starting opsechat services..."
compose_exec "${UP_ARGS[@]}"

if [[ "$NO_WAIT" -eq 0 ]]; then
    echo "[*] Waiting for services to be visible in compose status..."
    end_time=$((SECONDS + WAIT_TIMEOUT))
    while (( SECONDS < end_time )); do
        if services_appear_running; then
            break
        fi
        sleep 2
    done
fi

if services_appear_running; then
    echo "[OK] Services are running: opsechat-tor and opsechat-app"
else
    echo "[WARN] Services started, but status did not stabilize yet"
fi

echo ""
echo "[*] Next commands:"
echo "    ./verify-setup.sh --runtime $COMPOSE_RUNTIME"
echo "    $COMPOSE_DISPLAY -f $COMPOSE_FILE logs opsechat"
echo "    $COMPOSE_DISPLAY -f $COMPOSE_FILE logs -f"
echo "    ./compose-down.sh --runtime $COMPOSE_RUNTIME"
echo ""

if [[ "$FOLLOW_LOGS" -eq 1 ]]; then
    echo "[*] Following opsechat logs (Ctrl+C to stop)..."
    compose_exec logs -f --tail=100 opsechat
fi
