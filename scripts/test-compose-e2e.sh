#!/usr/bin/env bash
# Container-up-to-container-down end-to-end test.
#
# 1. Bring the compose stack up (podman or docker).
# 2. Poll the localhost admin proxy /health until ready (or fail).
# 3. Run the alpha Playwright specs against http://127.0.0.1:8080.
# 4. ALWAYS tear the stack back down via the EXIT trap.
#
# Use:
#   ./scripts/test-compose-e2e.sh
#
# Honour `OPSECHAT_BASE_URL` to override the admin-proxy URL (default
# http://127.0.0.1:8080).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_URL="${OPSECHAT_BASE_URL:-http://127.0.0.1:8080}"
HEALTH_URL="$BASE_URL/health"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"

cleanup() {
  echo
  echo "[compose-e2e] tearing stack down..."
  ./compose-down.sh || true
}
trap cleanup EXIT

echo "[compose-e2e] bringing stack up..."
./compose-up.sh

echo "[compose-e2e] waiting up to ${HEALTH_TIMEOUT}s for $HEALTH_URL ..."
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
while true; do
  if curl --silent --fail --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    echo "[compose-e2e] /health is green."
    break
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "[compose-e2e] FAILED: /health did not become green in time." >&2
    exit 1
  fi
  sleep 2
done

echo "[compose-e2e] running alpha Playwright suite against $BASE_URL ..."
OPSECHAT_BASE_URL="$BASE_URL" npx playwright test \
  --config=playwright-compose.config.js \
  --reporter=line

echo "[compose-e2e] success."
