#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PLAYWRIGHT_CACHE_DIR="${PROJECT_ROOT}/.cache/ms-playwright"
DRY_RUN=false
SKIP_NODE_SETUP=false
SKIP_PLAYWRIGHT_INSTALL=false
SKIP_TOR_INSTALL=false
VERIFY_ONLY=false

print_usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-dev-environment.sh [options]

Options:
  --dry-run            Print commands without executing them
  --skip-node          Skip npm dependency installation
  --skip-playwright    Skip Playwright browser installation
  --skip-tor           Skip Tor package installation checks
  --verify-only        Only run scripts/check-dev-env.py
  -h, --help           Show this help message
EOF
}

log() {
  echo "[*] $*"
}

run_cmd() {
  if [ "${DRY_RUN}" = true ]; then
    echo "[dry-run] $*"
    return 0
  fi

  "$@"
}

require_command() {
  local cmd="$1"
  local human_name="$2"

  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "[!] ${human_name} is required but not installed"
    return 1
  fi

  return 0
}

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

  run_cmd "${cmd_prefix[@]}" apt-get update
  run_cmd "${cmd_prefix[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  return 0
}

ensure_venv_support() {
  if ! require_command python3 "Python 3"; then
    return 1
  fi

  if python3 -c "import venv" >/dev/null 2>&1; then
    return
  fi

  log "Installing python3-venv so project virtualenv creation works"
  if ! install_apt_packages_if_possible python3-venv; then
    echo "[!] Unable to install python3-venv automatically"
    return 1
  fi
}

install_tor_if_possible() {
  if [ "${SKIP_TOR_INSTALL}" = true ]; then
    log "Skipping Tor install per --skip-tor"
    return
  fi

  if command -v tor >/dev/null 2>&1; then
    log "Tor is already installed"
    return
  fi

  if install_apt_packages_if_possible tor; then
    return
  fi

  log "Skipping Tor install: need root or passwordless sudo"
}

run_node_setup() {
  if [ "${SKIP_NODE_SETUP}" = true ]; then
    log "Skipping Node.js setup per --skip-node"
    return
  fi

  if ! require_command npm "npm"; then
    exit 1
  fi

  (
    cd "${PROJECT_ROOT}"

    if [ -f package-lock.json ]; then
      run_cmd npm ci
    else
      run_cmd npm install
    fi

    if [ "${SKIP_PLAYWRIGHT_INSTALL}" = true ]; then
      log "Skipping Playwright install per --skip-playwright"
      return
    fi

    run_cmd env PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install --with-deps || \
      run_cmd env PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install
  )
}

run_environment_check() {
  if [ ! -f "${PROJECT_ROOT}/scripts/check-dev-env.py" ]; then
    echo "[!] scripts/check-dev-env.py not found. Skipping environment verification."
    return
  fi

  run_cmd env PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" \
    "${VENV_DIR}/bin/python" "${PROJECT_ROOT}/scripts/check-dev-env.py"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      ;;
    --skip-node)
      SKIP_NODE_SETUP=true
      SKIP_PLAYWRIGHT_INSTALL=true
      ;;
    --skip-playwright)
      SKIP_PLAYWRIGHT_INSTALL=true
      ;;
    --skip-tor)
      SKIP_TOR_INSTALL=true
      ;;
    --verify-only)
      VERIFY_ONLY=true
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "[!] Unknown option: $1"
      print_usage
      exit 1
      ;;
  esac
  shift
done

log "Bootstrapping development environment in ${PROJECT_ROOT}"

if [ "${VERIFY_ONLY}" = true ]; then
  run_environment_check
  exit 0
fi

run_cmd mkdir -p "${PLAYWRIGHT_CACHE_DIR}"

if ! ensure_venv_support; then
  echo "[!] Failed to ensure Python venv support. Cannot proceed."
  exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
  run_cmd python3 -m venv "${VENV_DIR}"
else
  log "Using existing virtual environment at ${VENV_DIR}"
fi

run_cmd "${VENV_DIR}/bin/python" -m pip install --upgrade pip

if [ ! -f "${PROJECT_ROOT}/requirements.txt" ]; then
  echo "[!] requirements.txt not found in ${PROJECT_ROOT}"
  exit 1
fi
if [ ! -f "${PROJECT_ROOT}/requirements-dev.txt" ]; then
  echo "[!] requirements-dev.txt not found in ${PROJECT_ROOT}"
  exit 1
fi

run_cmd "${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt" \
  -r "${PROJECT_ROOT}/requirements-dev.txt" -e "${PROJECT_ROOT}"

install_tor_if_possible

run_node_setup
run_environment_check
