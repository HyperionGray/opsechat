#!/usr/bin/env bash
# Script to start opsechat services with health-based readiness checks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/compose-common.sh
source "$SCRIPT_DIR/compose-common.sh"

setup_compose_paths "$SCRIPT_DIR"
detect_compose_runtime

echo "[*] Using ${COMPOSE_LABEL}"
echo "[*] Starting opsechat services..."
run_compose up -d

echo
echo "[*] Waiting for Tor container readiness..."
if wait_for_container_ready "opsechat-tor" 60; then
  echo "[+] Tor container is ready"
else
  echo "[!] Tor container did not become ready within 60 seconds"
  run_compose logs tor || true
  exit 1
fi

echo "[*] Waiting for opsechat app container readiness..."
if wait_for_container_ready "opsechat-app" 90; then
  echo "[+] Opsechat app container is ready"
else
  echo "[!] Opsechat app container did not become ready within 90 seconds"
  run_compose logs opsechat || true
  exit 1
fi

echo "[*] Validating /health endpoint inside app container..."
health_ok=0
for _ in 1 2 3 4 5; do
  if check_app_health_endpoint; then
    health_ok=1
    break
  fi
  sleep 2
done

if [ "$health_ok" -eq 1 ]; then
  echo "[+] /health endpoint is responding"
else
  echo "[!] /health endpoint failed inside container"
  run_compose logs opsechat || true
  exit 1
fi

echo
echo "[*] Startup checks passed."
echo "[*] To view the onion address, run:"
echo "    ${COMPOSE_CMD[*]} -f ${COMPOSE_FILE} logs opsechat"
echo
echo "[*] To verify the setup is working, run:"
echo "    ./verify-setup.sh"
echo
echo "[*] To view all logs in real-time, run:"
echo "    ${COMPOSE_CMD[*]} -f ${COMPOSE_FILE} logs -f"
echo
echo "[*] To stop services, run:"
echo "    ./compose-down.sh"
echo
