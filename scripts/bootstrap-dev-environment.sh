#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PLAYWRIGHT_CACHE_DIR="${PROJECT_ROOT}/.cache/ms-playwright"
SKIP_PYTHON=0
SKIP_NODE=0
SKIP_PLAYWRIGHT=0
SKIP_TOR=0
SKIP_VERIFY=0
CHECK_ONLY=0
RECREATE_VENV=0
ALLOW_SYSTEM_PACKAGES=1

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-dev-environment.sh [options]

Options:
  --check-only            Only run environment verification checks.
  --skip-python           Skip Python virtualenv and pip dependency setup.
  --skip-node             Skip npm dependency and Playwright setup.
  --skip-playwright       Skip Playwright browser installation.
  --skip-tor              Skip Tor installation attempt.
  --skip-verify           Skip final environment verification script.
  --recreate-venv         Delete and recreate .venv before installing dependencies.
  --skip-system-packages  Never attempt apt-based package installs.
  -h, --help              Show this help text.
EOF
}

log() {
  echo "[*] $*"
}

warn() {
  echo "[!] $*" >&2
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --check-only)
        CHECK_ONLY=1
        ;;
      --skip-python)
        SKIP_PYTHON=1
        ;;
      --skip-node)
        SKIP_NODE=1
        ;;
      --skip-playwright)
        SKIP_PLAYWRIGHT=1
        ;;
      --skip-tor)
        SKIP_TOR=1
        ;;
      --skip-verify)
        SKIP_VERIFY=1
        ;;
      --recreate-venv)
        RECREATE_VENV=1
        ;;
      --skip-system-packages)
        ALLOW_SYSTEM_PACKAGES=0
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
    shift
  done

  if [ "${SKIP_NODE}" -eq 1 ]; then
    SKIP_PLAYWRIGHT=1
  fi
}

install_apt_packages_if_possible() {
  if [ "${ALLOW_SYSTEM_PACKAGES}" -ne 1 ]; then
    return 1
  fi

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

  if [ -n "${cmd_prefix}" ]; then
    ${cmd_prefix} apt-get update
    ${cmd_prefix} env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  else
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  fi

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

ensure_command() {
  local command_name="$1"
  local friendly_name="$2"

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    warn "${friendly_name} is required but not installed."
    return 1
  fi
}

bootstrap_python() {
  ensure_command python3 "Python 3"

  if ! ensure_venv_support; then
    warn "Failed to ensure Python venv support. Cannot proceed with Python setup."
    return 1
  fi

  if [ "${RECREATE_VENV}" -eq 1 ] && [ -d "${VENV_DIR}" ]; then
    log "Removing existing virtual environment at ${VENV_DIR}"
    rm -rf "${VENV_DIR}"
  fi

  if [ ! -d "${VENV_DIR}" ]; then
    log "Creating virtual environment at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  else
    log "Using existing virtual environment at ${VENV_DIR}"
  fi

  "${VENV_DIR}/bin/python" -m pip install --upgrade pip

  if [ ! -f "${PROJECT_ROOT}/requirements.txt" ]; then
    warn "requirements.txt not found in ${PROJECT_ROOT}"
    return 1
  fi

  if [ ! -f "${PROJECT_ROOT}/requirements-dev.txt" ]; then
    warn "requirements-dev.txt not found in ${PROJECT_ROOT}"
    return 1
  fi

  "${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt" -r "${PROJECT_ROOT}/requirements-dev.txt" -e "${PROJECT_ROOT}"
}

bootstrap_node() {
  ensure_command node "Node.js"
  ensure_command npm "npm"
  ensure_command npx "npx"

  (
    cd "${PROJECT_ROOT}"

    if [ -f package-lock.json ]; then
      log "Installing Node dependencies via npm ci"
      npm ci
    else
      log "Installing Node dependencies via npm install"
      npm install
    fi

    if [ "${SKIP_PLAYWRIGHT}" -eq 1 ]; then
      log "Skipping Playwright browser install (--skip-playwright)"
    else
      log "Installing Playwright browsers"
      PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install --with-deps || \
        PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install
    fi
  )
}

verify_environment() {
  local checker_path="${PROJECT_ROOT}/scripts/check-dev-env.py"
  local python_for_checks="python3"

  if [ -x "${VENV_DIR}/bin/python" ]; then
    python_for_checks="${VENV_DIR}/bin/python"
  fi

  if [ ! -f "${checker_path}" ]; then
    warn "scripts/check-dev-env.py not found. Skipping environment verification."
    return 0
  fi

  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" "${python_for_checks}" "${checker_path}"
}

main() {
  parse_args "$@"

  log "Bootstrapping development environment in ${PROJECT_ROOT}"
  mkdir -p "${PLAYWRIGHT_CACHE_DIR}"

  if [ "${CHECK_ONLY}" -eq 1 ]; then
    verify_environment
    return $?
  fi

  if [ "${SKIP_PYTHON}" -eq 1 ]; then
    log "Skipping Python setup (--skip-python)"
  else
    bootstrap_python
  fi

  if [ "${SKIP_TOR}" -eq 1 ]; then
    log "Skipping Tor installation attempt (--skip-tor)"
  else
    install_tor_if_possible
  fi

  if [ "${SKIP_NODE}" -eq 1 ]; then
    log "Skipping Node.js setup (--skip-node)"
  else
    bootstrap_node
  fi

  if [ "${SKIP_VERIFY}" -eq 1 ]; then
    log "Skipping final environment verification (--skip-verify)"
  else
    verify_environment
  fi

  log "Bootstrap complete."
}

main "$@"
