#!/bin/bash
# opsechat Uninstall Script
# This script removes opsechat installation while preserving system packages

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="${HOME}/opsechat"

# Print functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "========================================"
    echo "$1"
    echo "========================================"
    echo ""
}

# Confirm uninstallation
confirm_uninstall() {
    print_header "opsechat Uninstaller"
    
    echo "This script will remove the opsechat installation from:"
    echo "  $INSTALL_DIR"
    echo ""
    echo "Note: System packages (Python, Tor, Git) will NOT be removed."
    echo ""
    
    read -p "Are you sure you want to uninstall opsechat? (yes/no) " -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Uninstallation cancelled"
        exit 0
    fi
}

# Stop running processes
stop_processes() {
    print_header "Stopping running processes"
    
    # Find and kill any running runserver.py processes
    if pgrep -f "python.*runserver.py" > /dev/null; then
        print_info "Stopping opsechat server..."
        pkill -f "python.*runserver.py" || true
        sleep 1
        print_info "Server stopped"
    else
        print_info "No running opsechat processes found"
    fi
}

# Remove installation directory
remove_installation() {
    print_header "Removing installation"
    
    if [ -d "$INSTALL_DIR" ]; then
        print_info "Removing $INSTALL_DIR..."
        rm -rf "$INSTALL_DIR"
        print_info "Installation directory removed"
    else
        print_warning "Installation directory not found at $INSTALL_DIR"
    fi
}

# Remove Tor configuration (optional)
remove_tor_config() {
    print_header "Tor Configuration"
    
    echo "Do you want to remove opsechat-specific Tor configuration?"
    echo "This will remove the ControlPort settings from /etc/tor/torrc"
    echo "Note: This requires sudo access"
    echo ""
    read -p "Remove Tor configuration? (y/n) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        TOR_CONFIG="/etc/tor/torrc"
        
        if [ -f "$TOR_CONFIG" ]; then
            if grep -q "# opsechat configuration" "$TOR_CONFIG" 2>/dev/null; then
                print_info "Creating backup of Tor configuration..."
                sudo cp "$TOR_CONFIG" "${TOR_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
                
                print_info "Removing opsechat configuration from Tor..."
                # Remove opsechat configuration lines
                sudo sed -i '/# opsechat configuration/,+2d' "$TOR_CONFIG"
                
                print_info "Restarting Tor service..."
                sudo systemctl restart tor 2>/dev/null || true
                
                print_info "Tor configuration cleaned up"
            else
                print_info "No opsechat-specific Tor configuration found"
            fi
        else
            print_warning "Tor configuration file not found"
        fi
    else
        print_info "Tor configuration preserved"
    fi
}

# Verify uninstallation
verify_uninstall() {
    print_header "Verifying uninstallation"
    
    if [ -d "$INSTALL_DIR" ]; then
        print_error "Installation directory still exists"
        return 1
    else
        print_info "✓ Installation directory removed"
    fi
    
    if pgrep -f "python.*runserver.py" > /dev/null; then
        print_warning "⚠ opsechat processes still running"
        return 1
    else
        print_info "✓ No running processes"
    fi
    
    return 0
}

# Print completion message
print_completion() {
    print_header "Uninstallation Complete"
    
    cat << EOF
opsechat has been uninstalled successfully.

What was removed:
- Installation directory: $INSTALL_DIR
- Python virtual environment
- Launcher scripts

What was preserved:
- System packages (Python, Tor, Git)
- System Tor configuration (if not explicitly removed)

Note: If you want to remove system packages, use your package manager:
    Ubuntu/Debian: sudo apt-get remove tor python3
    RHEL/CentOS/Fedora: sudo dnf remove tor python3
    Arch: sudo pacman -R tor python

Thank you for using opsechat!

EOF
}

# Main uninstallation flow
main() {
    confirm_uninstall
    stop_processes
    remove_installation
    remove_tor_config
    
    echo ""
    if verify_uninstall; then
        print_completion
        exit 0
    else
        print_error "Uninstallation completed with warnings. Please review the output above."
        exit 1
    fi
}

# Handle interruption
trap 'echo ""; print_error "Uninstallation interrupted"; exit 1' INT TERM

# Run main function
main "$@"
