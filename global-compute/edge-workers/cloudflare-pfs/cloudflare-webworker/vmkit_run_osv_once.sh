#!/usr/bin/env bash
# scripts/swarm/vmkit_run_osv_once.sh
# Run an OSv guest_init image directly via VMKit for a one-shot test (outside orchestrator)
# Usage env:
#   CMD="/bin/echo hello" IMAGE=/path/to/osv.img ./scripts/swarm/vmkit_run_osv_once.sh
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
VMKIT_BIN="${VMKIT_BIN:-vmkit}"
: "${CMD:?CMD required}"

find_osv_image() {
  local base="$ROOT_DIR/osv/guest_init/.capstan"
  if [ -d "$base" ]; then
    local p
    p=$(find "$base" -type f \( -name "*.img" -o -name "loader.img" \) 2>/dev/null | head -n1 || true)
    if [ -n "$p" ]; then
      echo "$p"; return 0
    fi
  fi
  return 1
}

IMAGE="${IMAGE:-}"
if [ -z "$IMAGE" ]; then
  if IMAGE_PATH=$(find_osv_image); then
    IMAGE="$IMAGE_PATH"
  else
    echo "Could not autodetect OSv image. Set IMAGE=/path/to/osv.img or run 'pf swarm-osv-build-guest-init' first." >&2
    exit 2
  fi
fi

exec "$VMKIT_BIN" run --image "$IMAGE" --cmd "/guest_init.sh" --env "CMD=${CMD}"
