#!/bin/bash
# Verification script for Docker/Podman compose setup
# This script checks that the containerized opsechat is running correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine which compose tool is available
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}[!] Error: Neither podman-compose nor docker-compose found.${NC}"
    exit 1
fi

echo "========================================"
echo "Opsechat Container Verification"
echo "========================================"
echo ""

# Check if containers are running
echo -e "${YELLOW}[*]${NC} Checking container status..."
if $COMPOSE_CMD ps | grep -q "opsechat-tor"; then
    echo -e "${GREEN}[✓]${NC} Tor container is running"
else
    echo -e "${RED}[✗]${NC} Tor container is not running"
    echo "    Run: ./compose-up.sh"
    exit 1
fi

if $COMPOSE_CMD ps | grep -q "opsechat-app"; then
    echo -e "${GREEN}[✓]${NC} Opsechat container is running"
else
    echo -e "${RED}[✗]${NC} Opsechat container is not running"
    echo "    Run: ./compose-up.sh"
    exit 1
fi

# Check Tor health
echo ""
echo -e "${YELLOW}[*]${NC} Checking Tor service health..."
if $COMPOSE_CMD exec -T tor nc -z localhost 9051 2>/dev/null; then
    echo -e "${GREEN}[✓]${NC} Tor control port is accessible (9051)"
else
    echo -e "${RED}[✗]${NC} Tor control port is not accessible"
fi

if $COMPOSE_CMD exec -T tor nc -z localhost 9050 2>/dev/null; then
    echo -e "${GREEN}[✓]${NC} Tor SOCKS port is accessible (9050)"
else
    echo -e "${RED}[✗]${NC} Tor SOCKS port is not accessible"
fi

# Check if opsechat generated an onion address
echo ""
echo -e "${YELLOW}[*]${NC} Checking for hidden service address..."
# Tor v3 onion addresses are 56 characters followed by .onion
# Pattern matches: 56 alphanumeric chars + .onion/ + 32 char path
LOGS=$($COMPOSE_CMD logs opsechat 2>/dev/null | grep -o "[a-z0-9]\{56\}\.onion/[a-zA-Z0-9]\{32\}" | head -1)

if [ ! -z "$LOGS" ]; then
    echo -e "${GREEN}[✓]${NC} Hidden service is running"
    echo ""
    echo "========================================"
    echo -e "${GREEN}Your opsechat service is available at:${NC}"
    echo -e "${GREEN}$LOGS${NC}"
    echo "========================================"
    echo ""
    echo "Open this URL in Tor Browser to access your chat!"
else
    echo -e "${YELLOW}[⚠]${NC} Hidden service address not found in logs yet"
    echo "    This may take a minute or two..."
    echo "    Run: $COMPOSE_CMD logs opsechat"
fi

# Check network connectivity
echo ""
echo -e "${YELLOW}[*]${NC} Checking container network..."
if $COMPOSE_CMD exec -T opsechat ping -c 1 tor &>/dev/null; then
    echo -e "${GREEN}[✓]${NC} Opsechat can reach Tor container"
else
    echo -e "${YELLOW}[⚠]${NC} Network connectivity check failed (may not be critical)"
fi

# Resource usage
echo ""
echo -e "${YELLOW}[*]${NC} Container resource usage:"
$COMPOSE_CMD ps

echo ""
echo "========================================"
echo -e "${GREEN}Verification complete!${NC}"
echo "========================================"
echo ""
echo "Useful commands:"
echo "  View logs:          $COMPOSE_CMD logs -f"
echo "  Restart services:   ./compose-down.sh && ./compose-up.sh"
echo "  Stop services:      ./compose-down.sh"
echo ""
