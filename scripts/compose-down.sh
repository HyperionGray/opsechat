#!/bin/bash
# Script to stop opsechat services with podman-compose or docker-compose.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/compose-common.sh"

SHOW_STATUS=false
REMOVE_VOLUMES=false

usage() {
    cat <<'EOF'
Usage: ./compose-down.sh [options]

Options:
  --runtime {auto|podman|docker}  Choose runtime backend (default: auto)
  --volumes                        Remove volumes as well (destructive)
  --status                         Show status after stop
  -h, --help                       Show this help text

Examples:
  ./compose-down.sh
  ./compose-down.sh --runtime podman --status
  ./compose-down.sh --volumes
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --runtime)
            shift
            [ $# -gt 0 ] || { echo "[!] Missing value for --runtime" >&2; exit 1; }
            set_compose_runtime "$1"
            ;;
        --volumes)
            REMOVE_VOLUMES=true
            ;;
        --status)
            SHOW_STATUS=true
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
echo "[*] Using $COMPOSE_DISPLAY"
echo "[*] Stopping opsechat services..."

if [ "$REMOVE_VOLUMES" = true ]; then
    compose_exec down -v
else
    compose_exec down
fi

echo
if [ "$REMOVE_VOLUMES" = true ]; then
    echo "[✓] Services and volumes removed"
else
    echo "[✓] Services stopped and removed"
fi

if [ "$SHOW_STATUS" = true ]; then
    echo
    echo "[*] Current service status:"
    compose_exec ps || true
fi

echo
echo "[*] Start again with:"
echo "    ./compose-up.sh --runtime $COMPOSE_RUNTIME"
echo
