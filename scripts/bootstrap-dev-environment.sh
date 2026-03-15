#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PLAYWRIGHT_CACHE_DIR="${PROJECT_ROOT}/.cache/ms-playwright"
SKIP_NODE=0
SKIP_PLAYWRIGHT=0
SKIP_TOR=0
VERIFY_ONLY=0
RECREATE_VENV=0

usage() {
  cat <<EOF
Usage: ./scripts/bootstrap-dev-environment.sh [options]

Options:
  --skip-node         Skip npm dependency installation
  --skip-playwright   Skip Playwright browser installation
  --skip-tor          Skip Tor installation attempt
  --verify-only       Only run scripts/check-dev-env.py
  --recreate-venv     Remove and recreate .venv before installing
  -h, --help          Show this help message
EOF
}

log() {
  echo "[*] $*"
}

warn() {
  echo "[!] $*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-node)
      SKIP_NODE=1
      shift
      ;;
    --skip-playwright)
      SKIP_PLAYWRIGHT=1
      shift
      ;;
    --skip-tor)
      SKIP_TOR=1
      shift
      ;;
    --verify-only)
      VERIFY_ONLY=1
      shift
      ;;
    --recreate-venv)
      RECREATE_VENV=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      warn "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

install_apt_packages_if_possible() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi

  local -a cmd_prefix=()
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
      cmd_prefix=(sudo)
    else
      return 1
    fi
  fi

  "${cmd_prefix[@]}" apt-get update
  "${cmd_prefix[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  return 0
}

ensure_venv_support() {
  if python3 -c "import venv" >/dev/null 2>&1; then
    return
  fi

  log "Installing python3-venv so project virtualenv creation works"
  if ! install_apt_packages_if_possible python3-venv; then
    warn "Unable to install python3-venv automatically"
    return 1
  fi
}

install_tor_if_possible() {
  if command -v tor >/dev/null 2>&1; then
    log "Tor is already installed"
    return
  fi

  if install_apt_packages_if_possible tor; then
    return
  fi

  log "Skipping Tor install: need root or passwordless sudo"
}

ensure_requirements_files() {
  if [ ! -f "${PROJECT_ROOT}/requirements.txt" ]; then
    warn "requirements.txt not found in ${PROJECT_ROOT}"
    return 1
  fi
  if [ ! -f "${PROJECT_ROOT}/requirements-dev.txt" ]; then
    warn "requirements-dev.txt not found in ${PROJECT_ROOT}"
    return 1
  fi
}

install_python_deps() {
  if [ "${RECREATE_VENV}" -eq 1 ] && [ -d "${VENV_DIR}" ]; then
    log "Recreating existing virtualenv at ${VENV_DIR}"
    rm -rf "${VENV_DIR}"
  fi

  if [ ! -x "${VENV_DIR}/bin/python" ]; then
    log "Creating virtualenv at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  else
    log "Reusing existing virtualenv at ${VENV_DIR}"
  fi

  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  ensure_requirements_files
  "${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt" -r "${PROJECT_ROOT}/requirements-dev.txt" -e "${PROJECT_ROOT}"
}

install_node_deps() {
  if ! command -v npm >/dev/null 2>&1; then
    warn "npm is not available; cannot install Node dependencies."
    return 1
  fi

  (
    cd "${PROJECT_ROOT}"
    if [ -f package-lock.json ]; then
      npm ci
    else
      npm install
    fi
  )
}

install_playwright() {
  if [ "${SKIP_PLAYWRIGHT}" -eq 1 ]; then
    log "Skipping Playwright browser install (--skip-playwright)"
    return
  fi

  if ! command -v npx >/dev/null 2>&1; then
    warn "npx is not available; skipping Playwright browser install."
    return
  fi

  (
    cd "${PROJECT_ROOT}"
    PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install --with-deps || \
      PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install
  )
}

run_environment_verification() {
  if [ ! -f "${PROJECT_ROOT}/scripts/check-dev-env.py" ]; then
    warn "scripts/check-dev-env.py not found. Skipping environment verification."
    return
  fi

  local python_bin="python3"
  if [ -x "${VENV_DIR}/bin/python" ]; then
    python_bin="${VENV_DIR}/bin/python"
  fi

  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" "${python_bin}" "${PROJECT_ROOT}/scripts/check-dev-env.py"
}

log "Bootstrapping development environment in ${PROJECT_ROOT}"

mkdir -p "${PLAYWRIGHT_CACHE_DIR}"

if [ "${VERIFY_ONLY}" -eq 1 ]; then
  log "Running verification only (--verify-only)"
  run_environment_verification
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  warn "python3 is required but not found"
  exit 1
fi

if ! ensure_venv_support; then
  warn "Failed to ensure Python venv support. Cannot proceed."
  exit 1
fi

install_python_deps

if [ "${SKIP_TOR}" -eq 0 ]; then
  install_tor_if_possible
else
  log "Skipping Tor install (--skip-tor)"
fi

if [ "${SKIP_NODE}" -eq 0 ]; then
  install_node_deps
  install_playwright
else
  log "Skipping Node dependency installation (--skip-node)"
fi

run_environment_verification
