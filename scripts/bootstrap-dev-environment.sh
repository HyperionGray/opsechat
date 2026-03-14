#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PLAYWRIGHT_CACHE_DIR="${PROJECT_ROOT}/.cache/ms-playwright"

install_apt_packages_if_possible() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi

  local cmd_prefix=""
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
      cmd_prefix="sudo"
    else
      return 1
    fi
  fi
  ${cmd_prefix} apt-get update
  ${cmd_prefix} DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  return 0
}

ensure_venv_support() {
  if python3 -c "import venv" >/dev/null 2>&1; then
    return
  fi

  echo "[*] Installing python3-venv so project virtualenv creation works"
  if ! install_apt_packages_if_possible python3-venv; then
    echo "[!] Unable to install python3-venv automatically"
    return 1
  fi
}

install_tor_if_possible() {
  if command -v tor >/dev/null 2>&1; then
    echo "[*] Tor is already installed"
    return
  fi

  if install_apt_packages_if_possible tor; then
    return
  fi

  echo "[*] Skipping Tor install: need root or passwordless sudo"
}

echo "[*] Bootstrapping development environment in ${PROJECT_ROOT}"

mkdir -p "${PLAYWRIGHT_CACHE_DIR}"

if ! ensure_venv_support; then
  echo "[!] Failed to ensure Python venv support. Cannot proceed."
  exit 1
fi

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
if [ ! -f "${PROJECT_ROOT}/requirements.txt" ]; then
  echo "[!] requirements.txt not found in ${PROJECT_ROOT}"
  exit 1
fi
if [ ! -f "${PROJECT_ROOT}/requirements-dev.txt" ]; then
  echo "[!] requirements-dev.txt not found in ${PROJECT_ROOT}"
  exit 1
fi

"/${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt" -r "${PROJECT_ROOT}/requirements-dev.txt" -e "${PROJECT_ROOT}"

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

if [ ! -f "${PROJECT_ROOT}/scripts/check-dev-env.py" ]; then
  echo "[!] scripts/check-dev-env.py not found. Skipping environment verification."
else
  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" "${VENV_DIR}/bin/python" "${PROJECT_ROOT}/scripts/check-dev-env.py"
fi
