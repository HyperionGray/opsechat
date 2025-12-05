#!/bin/bash
# Quadlet setup script for opsechat
# Installs systemd quadlet files and configures services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUADLET_DIR="$SCRIPT_DIR/quadlets"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[!]${NC} $1"
}

check_requirements() {
    print_status "Checking requirements..."
    
    # Check systemd version
    if ! command -v systemctl &> /dev/null; then
        print_error "systemctl not found. This system doesn't appear to use systemd."
        exit 1
    fi
    
    # Check podman
    if ! command -v podman &> /dev/null; then
        print_error "podman not found. Please install podman first."
        print_status "Install with: sudo apt install podman (Ubuntu/Debian) or sudo dnf install podman (Fedora/RHEL)"
        exit 1
    fi
    
    # Check systemd version for quadlet support
    SYSTEMD_VERSION=$(systemctl --version | head -n1 | awk '{print $2}')
    if [ "$SYSTEMD_VERSION" -lt 247 ]; then
        print_warning "systemd version $SYSTEMD_VERSION detected. Quadlets require systemd 247+."
        print_warning "Quadlets may not work properly on this system."
    else
        print_success "systemd version $SYSTEMD_VERSION supports quadlets"
    fi
    
    print_success "Requirements check passed"
}

setup_directories() {
    print_status "Setting up directories..."
    
    # Create user systemd directory
    USER_SYSTEMD_DIR="$HOME/.config/containers/systemd"
    mkdir -p "$USER_SYSTEMD_DIR"
    print_success "Created $USER_SYSTEMD_DIR"
    
    # Create opsechat config directory
    OPSECHAT_CONFIG_DIR="$HOME/opsechat"
    mkdir -p "$OPSECHAT_CONFIG_DIR"
    print_success "Created $OPSECHAT_CONFIG_DIR"
}

install_quadlets() {
    print_status "Installing quadlet files..."
    
    USER_SYSTEMD_DIR="$HOME/.config/containers/systemd"
    
    # Copy quadlet files
    for file in "$QUADLET_DIR"/*.container "$QUADLET_DIR"/*.network "$QUADLET_DIR"/*.service "$QUADLET_DIR"/*.timer; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            print_status "Installing $filename"
            cp "$file" "$USER_SYSTEMD_DIR/"
            print_success "Installed $filename"
        fi
    done
    
    # Copy torrc
    TORRC_SOURCE="$SCRIPT_DIR/torrc"
    TORRC_DEST="$HOME/opsechat/torrc"
    
    if [ -f "$TORRC_SOURCE" ]; then
        cp "$TORRC_SOURCE" "$TORRC_DEST"
        print_success "Copied torrc to $TORRC_DEST"
    else
        print_error "torrc file not found at $TORRC_SOURCE"
        exit 1
    fi
}

build_image() {
    print_status "Building opsechat container image..."
    
    cd "$SCRIPT_DIR"
    
    if podman build -t localhost/opsechat:latest .; then
        print_success "Container image built successfully"
    else
        print_error "Failed to build container image"
        exit 1
    fi
}

enable_services() {
    print_status "Enabling and starting systemd services..."
    
    # Reload systemd daemon
    systemctl --user daemon-reload
    print_success "Reloaded systemd daemon"
    
    # Enable and start services in order
    SERVICES=(
        "opsechat-network.service"
        "opsechat-tor.service" 
        "opsechat-app.service"
    )
    
    for service in "${SERVICES[@]}"; do
        print_status "Enabling $service"
        if systemctl --user enable "$service"; then
            print_success "Enabled $service"
        else
            print_error "Failed to enable $service"
            exit 1
        fi
        
        print_status "Starting $service"
        if systemctl --user start "$service"; then
            print_success "Started $service"
        else
            print_error "Failed to start $service"
            print_status "Checking service status..."
            systemctl --user status "$service" --no-pager
            exit 1
        fi
        
        # Wait a moment between services
        sleep 2
    done
    
    # Enable cleanup timer
    print_status "Enabling cleanup timer"
    systemctl --user enable opsechat-cleanup.timer
    systemctl --user start opsechat-cleanup.timer
    print_success "Enabled cleanup timer"
}

enable_lingering() {
    print_status "Checking user lingering..."
    
    if loginctl show-user "$USER" | grep -q "Linger=yes"; then
        print_success "User lingering already enabled"
    else
        print_warning "User lingering not enabled"
        print_status "Attempting to enable lingering..."
        
        if sudo loginctl enable-linger "$USER" 2>/dev/null; then
            print_success "Enabled user lingering"
            print_status "Services will now start automatically on boot"
        else
            print_warning "Could not enable lingering (requires sudo)"
            print_warning "Services will not start automatically on boot"
            print_status "To enable manually: sudo loginctl enable-linger $USER"
        fi
    fi
}

wait_for_onion() {
    print_status "Waiting for onion service to be created..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if journalctl --user -u opsechat-app.service --no-pager | grep -q "Your service is available at:"; then
            print_success "Onion service created!"
            break
        fi
        
        attempt=$((attempt + 1))
        print_status "Waiting... ($attempt/$max_attempts)"
        sleep 5
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_warning "Timeout waiting for onion service"
        print_status "Check service logs: journalctl --user -u opsechat-app.service"
    fi
}

show_status() {
    print_status "Service status:"
    echo
    
    SERVICES=(
        "opsechat-network.service"
        "opsechat-tor.service"
        "opsechat-app.service"
        "opsechat-cleanup.timer"
    )
    
    for service in "${SERVICES[@]}"; do
        if systemctl --user is-active "$service" >/dev/null 2>&1; then
            print_success "$service is active"
        else
            print_error "$service is not active"
        fi
    done
    
    echo
    print_status "To view the onion address:"
    echo "  journalctl --user -u opsechat-app.service | grep 'Your service is available at:'"
    echo
    print_status "To view logs:"
    echo "  journalctl --user -u opsechat-app.service -f"
    echo
    print_status "To stop services:"
    echo "  systemctl --user stop opsechat-app.service opsechat-tor.service opsechat-network.service"
}

show_onion_address() {
    print_status "Looking for onion address..."
    
    local onion_line=$(journalctl --user -u opsechat-app.service --no-pager | grep "Your service is available at:" | tail -1)
    
    if [ -n "$onion_line" ]; then
        echo
        print_success "Onion service ready!"
        echo "$onion_line"
        echo
    else
        print_warning "Onion address not found in logs yet"
        print_status "Service may still be starting. Check logs with:"
        echo "  journalctl --user -u opsechat-app.service -f"
    fi
}

main() {
    echo "=== Opsechat Quadlet Setup ==="
    echo
    
    check_requirements
    setup_directories
    install_quadlets
    build_image
    enable_services
    enable_lingering
    wait_for_onion
    
    echo
    print_success "Quadlet setup completed successfully!"
    echo
    
    show_status
    show_onion_address
    
    echo
    print_status "Setup complete! Your opsechat service is now running with systemd."
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [options]"
        echo
        echo "Options:"
        echo "  --help, -h    Show this help message"
        echo "  --status      Show service status only"
        echo "  --onion       Show onion address only"
        echo
        echo "This script sets up opsechat to run with systemd quadlets."
        echo "It will:"
        echo "  - Install quadlet files to ~/.config/containers/systemd/"
        echo "  - Build the container image"
        echo "  - Enable and start systemd services"
        echo "  - Configure automatic startup (if possible)"
        exit 0
        ;;
    --status)
        show_status
        exit 0
        ;;
    --onion)
        show_onion_address
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        print_status "Use --help for usage information"
        exit 1
        ;;
esac