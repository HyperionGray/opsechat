#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PLAYWRIGHT_CACHE_DIR="${PROJECT_ROOT}/.cache/ms-playwright"
PROFILE="${BOOTSTRAP_PROFILE:-full}"
DRY_RUN=0
SKIP_VERIFY=0
RECREATE_VENV=0
SKIP_TOR=0

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-dev-environment.sh [options]

Bootstraps a local development environment for OpSecChat.

Options:
  --profile <full|python-only>  Setup profile (default: full)
  --python-only                 Shortcut for --profile python-only
  --recreate-venv               Delete and recreate .venv before install
  --skip-tor                    Skip optional Tor installation
  --skip-verify                 Skip scripts/check-dev-env.py at the end
  --dry-run                     Print actions without executing commands
  -h, --help                    Show this help message
EOF
}

log() {
  echo "[*] $*"
}

run_cmd() {
  if [ "${DRY_RUN}" -eq 1 ]; then
    echo "[dry-run] $*"
    return 0
  fi
  "$@"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --profile)
      if [ $# -lt 2 ]; then
        echo "[!] --profile requires a value (full|python-only)"
        exit 1
      fi
      PROFILE="$2"
      shift 2
      ;;
    --python-only)
      PROFILE="python-only"
      shift
      ;;
    --recreate-venv)
      RECREATE_VENV=1
      shift
      ;;
    --skip-tor)
      SKIP_TOR=1
      shift
      ;;
    --skip-verify)
      SKIP_VERIFY=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[!] Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [ "${PROFILE}" != "full" ] && [ "${PROFILE}" != "python-only" ]; then
  echo "[!] Invalid profile: ${PROFILE}. Valid values: full, python-only"
  exit 1
fi

install_apt_packages_if_possible() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi

  local cmd_prefix=()
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
      cmd_prefix=(sudo)
    else
      return 1
    fi
  fi

  if [ "${DRY_RUN}" -eq 1 ]; then
    echo "[dry-run] ${cmd_prefix[*]} apt-get update"
    echo "[dry-run] ${cmd_prefix[*]} env DEBIAN_FRONTEND=noninteractive apt-get install -y $*"
    return 0
  fi

  "${cmd_prefix[@]}" apt-get update
  "${cmd_prefix[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
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
  if [ "${SKIP_TOR}" -eq 1 ]; then
    log "Skipping Tor install (--skip-tor set)"
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

log "Bootstrapping development environment in ${PROJECT_ROOT}"
log "Using profile: ${PROFILE}"

run_cmd mkdir -p "${PLAYWRIGHT_CACHE_DIR}"

if ! ensure_venv_support; then
  echo "[!] Failed to ensure Python venv support. Cannot proceed."
  exit 1
fi

if [ -d "${VENV_DIR}" ] && [ "${RECREATE_VENV}" -eq 1 ]; then
  run_cmd rm -rf "${VENV_DIR}"
fi

if [ ! -d "${VENV_DIR}" ]; then
  run_cmd python3 -m venv "${VENV_DIR}"
else
  log "Using existing virtualenv at ${VENV_DIR}"
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

run_cmd "${VENV_DIR}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt" -r "${PROJECT_ROOT}/requirements-dev.txt" -e "${PROJECT_ROOT}"

install_tor_if_possible

if [ "${PROFILE}" = "full" ]; then
  if [ "${DRY_RUN}" -eq 0 ]; then
    for cmd in node npm npx; do
      if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "[!] ${cmd} is required for profile=full"
        exit 1
      fi
    done
  fi

  (
    cd "${PROJECT_ROOT}"

    if [ -f package-lock.json ]; then
      run_cmd npm ci
    else
      run_cmd npm install
    fi

    if [ "${DRY_RUN}" -eq 1 ]; then
      echo "[dry-run] env PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_CACHE_DIR} npx playwright install --with-deps"
      echo "[dry-run] (fallback) env PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_CACHE_DIR} npx playwright install"
    else
      env PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install --with-deps || \
        env PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" npx playwright install
    fi
  )
else
  log "Skipping Node.js/npm/Playwright steps for profile=${PROFILE}"
fi

if [ "${SKIP_VERIFY}" -eq 1 ]; then
  log "Skipping environment verification (--skip-verify set)"
elif [ ! -f "${PROJECT_ROOT}/scripts/check-dev-env.py" ]; then
  echo "[!] scripts/check-dev-env.py not found. Skipping environment verification."
else
  run_cmd env PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_CACHE_DIR}" \
    "${VENV_DIR}/bin/python" "${PROJECT_ROOT}/scripts/check-dev-env.py" \
    --profile "${PROFILE}"
fi
