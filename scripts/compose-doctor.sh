#!/bin/bash
# Unified diagnostics for compose-based deployment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/compose-common.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    WARN_COUNT=$((WARN_COUNT + 1))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

run_check() {
    local description="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        pass "$description"
    else
        fail "$description"
    fi
}

init_compose_context

echo "========================================"
echo "Opsechat Compose Doctor"
echo "========================================"

if require_compose_command; then
    pass "Compose command detected: $COMPOSE_NAME"
else
    fail "Compose command detection"
    echo ""
    echo "Summary: ${PASS_COUNT} passed, ${WARN_COUNT} warnings, ${FAIL_COUNT} failed"
    exit 1
fi

if [ -f "$COMPOSE_FILE" ]; then
    pass "Compose file present: container-compose.yml"
else
    fail "Compose file present: container-compose.yml"
fi

if [ -L "$REPO_ROOT/docker-compose.yml" ]; then
    pass "Legacy docker-compose.yml symlink exists"
else
    warn "Legacy docker-compose.yml symlink missing (optional)"
fi

if [ -f "$REPO_ROOT/containers/torrc" ]; then
    pass "Tor configuration file exists"
else
    fail "Tor configuration file exists"
fi

if compose config >/dev/null 2>&1; then
    pass "Compose config parses successfully"
else
    fail "Compose config parses successfully"
fi

if compose ps >/dev/null 2>&1; then
    pass "Compose engine reachable"
else
    warn "Compose engine unreachable (containers may not be running)"
fi

if compose ps | grep -q "opsechat-tor"; then
    pass "Tor service appears in compose status"
else
    warn "Tor service not running yet (run ./compose-up.sh)"
fi

if compose ps | grep -q "opsechat-app"; then
    pass "Opsechat service appears in compose status"
else
    warn "Opsechat service not running yet (run ./compose-up.sh)"
fi

if compose ps | grep -q "opsechat-tor"; then
    if compose exec -T tor nc -z localhost 9051 >/dev/null 2>&1; then
        pass "Tor control port responds on 9051"
    else
        warn "Tor control port check failed (service may still be starting)"
    fi
fi

if compose ps | grep -q "opsechat-app"; then
    if compose exec -T opsechat sh -lc "command -v curl >/dev/null && curl --silent --fail http://127.0.0.1:5000/health >/dev/null"; then
        pass "Application /health endpoint reachable in container"
    else
        warn "Application /health endpoint not reachable yet"
    fi
fi

echo ""
echo "Summary: ${PASS_COUNT} passed, ${WARN_COUNT} warnings, ${FAIL_COUNT} failed"

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "Doctor result: FAILED"
    exit 1
fi

echo "Doctor result: OK"
