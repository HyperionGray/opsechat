#!/usr/bin/env bash
# Unified alpha test runner for OpSecChat.
#
# Default: runs the Python alpha test suite (pytest) and the Playwright
# alpha smoke (basic + tests/alpha/*.spec.js, headless across chromium /
# firefox / webkit).
#
# Usage:
#   ./run_tests.sh             # full alpha suite (python + playwright)
#   ./run_tests.sh --python    # python only
#   ./run_tests.sh --e2e       # playwright only
#   ./run_tests.sh --skip-e2e  # python only (alias)
#   ./run_tests.sh --legacy    # legacy playwright suite (out-of-alpha)
#   ./run_tests.sh --compose   # container-up-to-container-down E2E

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

RUN_PYTHON=true
RUN_E2E=true
RUN_LEGACY=false
RUN_COMPOSE=false

for arg in "$@"; do
  case "$arg" in
    --python)   RUN_PYTHON=true;  RUN_E2E=false ;;
    --e2e)      RUN_PYTHON=false; RUN_E2E=true ;;
    --skip-e2e) RUN_E2E=false ;;
    --legacy)   RUN_PYTHON=false; RUN_E2E=false; RUN_LEGACY=true ;;
    --compose)  RUN_PYTHON=false; RUN_E2E=false; RUN_COMPOSE=true ;;
    -h|--help)
      sed -n '2,15p' "$0" | sed 's/^# //; s/^#//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [ "$RUN_PYTHON" = true ]; then
  echo "=== Python alpha tests (pytest) ==="
  if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
  if "$PY" -m pytest --version >/dev/null 2>&1; then
    "$PY" -m pytest "$REPO_ROOT/tests" -q --no-header || FAILED=1
  else
    echo "[!] pytest not installed -- run: pip install -r requirements-dev.txt" >&2
    FAILED=1
  fi
fi

if [ "$RUN_E2E" = true ]; then
  echo
  echo "=== Playwright alpha tests ==="
  if command -v npx >/dev/null 2>&1 && [ -d "$REPO_ROOT/node_modules" ]; then
    npx playwright test --reporter=line || FAILED=1
  else
    echo "[*] Playwright not available -- run: npm ci && npx playwright install" >&2
  fi
fi

if [ "$RUN_LEGACY" = true ]; then
  echo
  echo "=== Playwright LEGACY tests (off-by-default) ==="
  npx playwright test --config=playwright-legacy.config.js --reporter=line || FAILED=1
fi

if [ "$RUN_COMPOSE" = true ]; then
  echo
  echo "=== Compose container-up-to-container-down E2E ==="
  bash "$REPO_ROOT/scripts/test-compose-e2e.sh" || FAILED=1
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "=== All executed tests passed ==="
  exit 0
else
  echo "=== Some tests failed ==="
  exit 1
fi
