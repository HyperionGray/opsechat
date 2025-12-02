#!/bin/bash
# install-quadlets.sh - Install Podman Quadlet files for opsechat
#
# This script installs the quadlet configuration files for systemd integration.
# Run this after building the container image.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUADLETS_DIR="${SCRIPT_DIR}/quadlets"

# Check if quadlets directory exists
if [ ! -d "$QUADLETS_DIR" ]; then
    echo -e "${RED}Error: quadlets directory not found at ${QUADLETS_DIR}${NC}"
    exit 1
fi

# Check for --system flag
SYSTEM_INSTALL=false
if [ "$1" = "--system" ] || [ "$1" = "-s" ]; then
    SYSTEM_INSTALL=true
fi

# Determine target directory
if [ "$SYSTEM_INSTALL" = true ]; then
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: System-wide installation requires root privileges${NC}"
        echo "Run: sudo $0 --system"
        exit 1
    fi
    TARGET_DIR="/etc/containers/systemd"
    SYSTEMCTL="systemctl"
else
    TARGET_DIR="${HOME}/.config/containers/systemd"
    SYSTEMCTL="systemctl --user"
fi

echo -e "${GREEN}=== Opsechat Quadlet Installer ===${NC}"
echo ""

# Create target directory
echo -e "${YELLOW}Creating target directory: ${TARGET_DIR}${NC}"
mkdir -p "$TARGET_DIR"

# Copy quadlet files
echo -e "${YELLOW}Installing quadlet files...${NC}"

for file in "$QUADLETS_DIR"/*.container "$QUADLETS_DIR"/*.network "$QUADLETS_DIR"/*.volume; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "  Installing: $filename"
        cp "$file" "$TARGET_DIR/"
    fi
done

# Update torrc path in opsechat-tor.container
echo ""
echo -e "${YELLOW}Updating torrc path in configuration...${NC}"
TORRC_PATH="${SCRIPT_DIR}/torrc"

if [ "$SYSTEM_INSTALL" = true ]; then
    # For system install, use absolute path
    sed -i "s|Volume=%h/opsechat/torrc|Volume=${TORRC_PATH}|g" "$TARGET_DIR/opsechat-tor.container"
else
    # For user install, keep %h but update path
    RELATIVE_PATH="${SCRIPT_DIR#$HOME/}"
    sed -i "s|Volume=%h/opsechat/torrc|Volume=%h/${RELATIVE_PATH}/torrc|g" "$TARGET_DIR/opsechat-tor.container"
fi
echo "  Updated torrc path to: ${TORRC_PATH}"

# Check if image exists
echo ""
echo -e "${YELLOW}Checking container image...${NC}"
if podman image exists localhost/opsechat:latest 2>/dev/null; then
    echo -e "  ${GREEN}Image found: localhost/opsechat:latest${NC}"
else
    echo -e "  ${YELLOW}Image not found. Building...${NC}"
    echo ""
    (cd "$SCRIPT_DIR" && podman build -t localhost/opsechat:latest .)
    echo ""
    echo -e "  ${GREEN}Image built successfully${NC}"
fi

# Reload systemd
echo ""
echo -e "${YELLOW}Reloading systemd...${NC}"
$SYSTEMCTL daemon-reload
echo -e "  ${GREEN}Systemd reloaded${NC}"

# Print instructions
echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Quadlet files installed to: $TARGET_DIR"
echo ""
echo "To start opsechat:"
echo "  $SYSTEMCTL start opsechat-app"
echo ""
echo "To enable auto-start at boot:"
echo "  $SYSTEMCTL enable opsechat-app"
if [ "$SYSTEM_INSTALL" = false ]; then
    echo "  loginctl enable-linger $USER"
fi
echo ""
echo "To view logs:"
if [ "$SYSTEM_INSTALL" = true ]; then
    echo "  journalctl -u opsechat-app -f"
else
    echo "  journalctl --user -u opsechat-app -f"
fi
echo ""
echo "For more information, see QUADLETS.md"
