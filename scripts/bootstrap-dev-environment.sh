#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PLAYWRIGHT_CACHE_DIR="${PROJECT_ROOT}/.cache/ms-playwright"

install_tor_if_possible() {
  if command -v tor >/dev/null 2>&1; then
    echo "[*] Tor is already installed"
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "[*] Skipping Tor install: apt-get is not available"
    return
  fi

  if [ "$(id -u)" -eq 0 ]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y tor
    return
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tor
    return
  fi

  echo "[*] Skipping Tor install: need root or passwordless sudo"
}

echo "[*] Bootstrapping development environment in ${PROJECT_ROOT}"

mkdir -p "${PLAYWRIGHT_CACHE_DIR}"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt"
"${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements-dev.txt"
"${VENV_DIR}/bin/pip" install -e "${PROJECT_ROOT}"

install_tor_if_possible

(
  cd "${PROJECT_ROOT}"

  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi

  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install --with-deps || \
    PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install
)

PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" "${VENV_DIR}/bin/python" "${PROJECT_ROOT}/scripts/check-dev-env.py"
