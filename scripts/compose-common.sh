#!/usr/bin/env bash
# Shared helpers for compose wrapper scripts.

set -u

resolve_repo_root() {
  local script_dir="$1"
  if [ -f "$script_dir/../container-compose.yml" ]; then
    (cd "$script_dir/.." && pwd)
  else
    echo "$script_dir"
  fi
}

setup_compose_paths() {
  local script_dir="$1"
  REPO_ROOT="$(resolve_repo_root "$script_dir")"
  COMPOSE_FILE="$REPO_ROOT/container-compose.yml"
}

detect_compose_runtime() {
  if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(podman-compose)
    COMPOSE_LABEL="podman-compose"
    CONTAINER_RUNTIME="podman"
    return 0
  fi

  if command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(podman compose)
    COMPOSE_LABEL="podman compose (plugin)"
    CONTAINER_RUNTIME="podman"
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
    COMPOSE_LABEL="docker-compose"
    CONTAINER_RUNTIME="docker"
    return 0
  fi

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
    COMPOSE_LABEL="docker compose (plugin)"
    CONTAINER_RUNTIME="docker"
    return 0
  fi

  echo "[!] Error: no supported compose tool found."
  echo "[!] Install podman-compose (preferred), podman compose, docker-compose, or docker compose."
  return 1
}

run_compose() {
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" "$@"
}

container_running() {
  local container_name="$1"
  local running
  running="$("$CONTAINER_RUNTIME" inspect -f '{{.State.Running}}' "$container_name" 2>/dev/null || true)"
  [ "$running" = "true" ]
}

container_health_status() {
  local container_name="$1"
  "$CONTAINER_RUNTIME" inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_name" 2>/dev/null || echo "unknown"
}

wait_for_container_ready() {
  local container_name="$1"
  local timeout_seconds="$2"
  local start="$SECONDS"
  local health

  while [ $((SECONDS - start)) -lt "$timeout_seconds" ]; do
    if container_running "$container_name"; then
      health="$(container_health_status "$container_name")"
      if [ "$health" = "healthy" ] || [ "$health" = "none" ]; then
        return 0
      fi
    fi
    sleep 2
  done

  return 1
}

check_app_health_endpoint() {
  "$CONTAINER_RUNTIME" exec opsechat-app curl --fail --silent http://127.0.0.1:5000/health >/dev/null
}
