#!/bin/bash
# Unified test runner for opsechat
# Runs Python unit tests and (optionally) Playwright smoke tests.
#
# Usage:
#   ./run_tests.sh            # run all available tests
#   ./run_tests.sh --python   # python tests only
#   ./run_tests.sh --e2e      # playwright smoke tests only
#   ./run_tests.sh --skip-e2e # python tests, skip playwright

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
RUN_PYTHON=true
RUN_E2E=true

for arg in "$@"; do
  case "$arg" in
    --python)   RUN_PYTHON=true; RUN_E2E=false ;;
    --e2e)      RUN_PYTHON=false; RUN_E2E=true ;;
    --skip-e2e) RUN_E2E=false ;;
    -h|--help)
      echo "Usage: $0 [--python|--e2e|--skip-e2e]"
      exit 0
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Python tests (pytest)
# ---------------------------------------------------------------------------
if $RUN_PYTHON; then
  echo "=== Python tests (pytest) ==="

  if command -v python3 &>/dev/null; then
    PYTHON=python3
  elif command -v python &>/dev/null; then
    PYTHON=python
  else
    echo "[!] python not found -- skipping Python tests"
    PYTHON=""
  fi

  if [ -n "$PYTHON" ]; then
    # Prefer venv if activated, otherwise try system pytest
    if $PYTHON -m pytest --version &>/dev/null; then
      $PYTHON -m pytest "$REPO_ROOT/tests" --tb=short -q || FAILED=1
    else
      echo "[!] pytest not installed -- run: pip install -r requirements-dev.txt"
      FAILED=1
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Playwright smoke tests
# ---------------------------------------------------------------------------
if $RUN_E2E; then
  echo ""
  echo "=== Playwright smoke tests ==="

  if command -v npx &>/dev/null && [ -d "$REPO_ROOT/node_modules" ]; then
    npx playwright test "$REPO_ROOT/tests/basic.spec.js" --reporter=line || FAILED=1
  else
    echo "[*] Playwright not available -- skipping (run: npm ci && npx playwright install)"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "=== All executed tests passed ==="
  exit 0
else
  echo "=== Some tests failed ==="
  exit 1
fi
