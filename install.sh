#!/bin/bash
# opsechat Installer Script (Deprecated)
# This script installs opsechat and all its dependencies on a clean Linux system
# Supports: Ubuntu/Debian, RHEL/CentOS/Fedora, Arch Linux
# NOTE: Container/quadlet deployments are the supported path. Set ALLOW_DEPRECATED_INSTALL=1 to proceed.

# Require explicit opt-in for deprecated native workflow
if [ "${ALLOW_DEPRECATED_INSTALL:-0}" != "1" ]; then
    echo "install.sh is deprecated. Use container/quadlet workflows."
    echo "If you must run it, export ALLOW_DEPRECATED_INSTALL=1."
    exit 1
fi

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="${HOME}/opsechat"
VENV_DIR="${INSTALL_DIR}/venv"

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

# Detect OS and package manager
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        print_error "Cannot detect operating system"
        exit 1
    fi
    
    print_info "Detected OS: $OS $VERSION"
    
    # Determine package manager
    if command -v apt-get &> /dev/null; then
        PKG_MANAGER="apt"
        INSTALL_CMD="sudo apt-get install -y"
        UPDATE_CMD="sudo apt-get update"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
        INSTALL_CMD="sudo yum install -y"
        UPDATE_CMD="sudo yum check-update || true"
    elif command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
        INSTALL_CMD="sudo dnf install -y"
        UPDATE_CMD="sudo dnf check-update || true"
    elif command -v pacman &> /dev/null; then
        PKG_MANAGER="pacman"
        INSTALL_CMD="sudo pacman -S --noconfirm"
        UPDATE_CMD="sudo pacman -Sy"
    else
        print_error "Unsupported package manager. Please install manually."
        exit 1
    fi
    
    print_info "Package manager: $PKG_MANAGER"
}

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root is not recommended. Please run as a regular user."
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Check for sudo access
check_sudo() {
    if ! sudo -v &> /dev/null; then
        print_error "This script requires sudo access to install system packages"
        exit 1
    fi
    print_info "Sudo access confirmed"
}

# Install Python 3
install_python() {
    print_header "Installing Python 3"
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_info "Python $PYTHON_VERSION is already installed"
            return 0
        else
            print_warning "Python $PYTHON_VERSION is installed but version 3.8+ is required"
        fi
    fi
    
    print_info "Installing Python 3..."
    
    case $PKG_MANAGER in
        apt)
            $INSTALL_CMD python3 python3-pip python3-venv
            ;;
        yum|dnf)
            $INSTALL_CMD python3 python3-pip python3-virtualenv
            ;;
        pacman)
            $INSTALL_CMD python python-pip
            ;;
        *)
            print_error "Unsupported package manager for Python installation"
            exit 1
            ;;
    esac
    
    # Verify installation
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_info "Python $PYTHON_VERSION installed successfully"
    else
        print_error "Python installation failed"
        exit 1
    fi
}

# Install Tor
install_tor() {
    print_header "Installing Tor"
    
    if command -v tor &> /dev/null; then
        TOR_VERSION=$(tor --version | head -n1 | awk '{print $3}')
        print_info "Tor $TOR_VERSION is already installed"
    else
        print_info "Installing Tor..."
        
        case $PKG_MANAGER in
            apt)
                $INSTALL_CMD tor
                ;;
            yum|dnf)
                # EPEL repository needed for RHEL/CentOS
                if [ "$PKG_MANAGER" = "yum" ]; then
                    sudo yum install -y epel-release || true
                fi
                $INSTALL_CMD tor
                ;;
            pacman)
                $INSTALL_CMD tor
                ;;
            *)
                print_error "Unsupported package manager for Tor installation"
                exit 1
                ;;
        esac
        
        # Verify installation
        if command -v tor &> /dev/null; then
            TOR_VERSION=$(tor --version | head -n1 | awk '{print $3}')
            print_info "Tor $TOR_VERSION installed successfully"
        else
            print_error "Tor installation failed"
            exit 1
        fi
    fi
}

# Configure Tor
configure_tor() {
    print_header "Configuring Tor"
    
    TOR_CONFIG="/etc/tor/torrc"
    
    # Check if control port is already configured
    if [ -f "$TOR_CONFIG" ]; then
        if grep -q "^ControlPort 9051" "$TOR_CONFIG" 2>/dev/null; then
            print_info "Tor ControlPort is already configured"
        else
            print_info "Configuring Tor ControlPort..."
            
            # Backup original config
            sudo cp "$TOR_CONFIG" "${TOR_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)" || true
            
            # Add ControlPort configuration
            echo "" | sudo tee -a "$TOR_CONFIG" > /dev/null
            echo "# opsechat configuration" | sudo tee -a "$TOR_CONFIG" > /dev/null
            echo "ControlPort 9051" | sudo tee -a "$TOR_CONFIG" > /dev/null
            echo "CookieAuthentication 0" | sudo tee -a "$TOR_CONFIG" > /dev/null
            
            print_info "Tor configuration updated"
            print_warning "Note: CookieAuthentication is disabled for simplicity. For better security,"
            print_warning "consider enabling password authentication. See SECURITY.md for details."
        fi
    else
        print_warning "Tor configuration file not found at $TOR_CONFIG"
        print_info "Creating basic Tor configuration..."
        
        sudo mkdir -p /etc/tor
        echo "ControlPort 9051" | sudo tee "$TOR_CONFIG" > /dev/null
        echo "CookieAuthentication 0" | sudo tee -a "$TOR_CONFIG" > /dev/null
    fi
    
    # Enable and start Tor service
    if command -v systemctl &> /dev/null; then
        print_info "Starting Tor service..."
        sudo systemctl enable tor 2>/dev/null || true
        sudo systemctl restart tor 2>/dev/null || true
        sleep 2
        
        if sudo systemctl is-active --quiet tor; then
            print_info "Tor service is running"
        else
            print_warning "Tor service may not be running. You might need to start it manually with: sudo systemctl start tor"
        fi
    else
        print_warning "systemctl not found. Please start Tor manually if needed"
    fi
}

# Clone or update repository
setup_repository() {
    print_header "Setting up opsechat repository"
    
    if [ -d "$INSTALL_DIR" ]; then
        print_info "Directory $INSTALL_DIR already exists"
        read -p "Do you want to update the existing installation? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cd "$INSTALL_DIR"
            if [ -d .git ]; then
                print_info "Updating repository..."
                # Explicitly pull from origin to avoid unexpected sources
                git pull origin "$(git rev-parse --abbrev-ref HEAD)" || git pull
            else
                print_warning "Directory exists but is not a git repository. Skipping update."
            fi
        fi
    else
        print_info "Cloning opsechat repository..."
        git clone https://github.com/HyperionGray/opsechat.git "$INSTALL_DIR"
    fi
    
    cd "$INSTALL_DIR"
}

# Setup Python virtual environment
setup_virtualenv() {
    print_header "Setting up Python virtual environment"
    
    cd "$INSTALL_DIR"
    
    if [ -d "$VENV_DIR" ]; then
        print_info "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing old virtual environment..."
            rm -rf "$VENV_DIR"
        else
            return 0
        fi
    fi
    
    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    if [ -f "$VENV_DIR/bin/activate" ]; then
        print_info "Virtual environment created successfully"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
}

# Install Python dependencies
install_python_dependencies() {
    print_header "Installing Python dependencies"
    
    cd "$INSTALL_DIR"
    
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        print_error "Virtual environment not found. Please run setup_virtualenv first."
        exit 1
    fi
    
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    print_info "Upgrading pip..."
    pip install --upgrade pip
    
    if [ -f "requirements.txt" ]; then
        print_info "Installing dependencies from requirements.txt..."
        pip install -r requirements.txt
    else
        print_error "requirements.txt not found"
        exit 1
    fi
    
    print_info "Python dependencies installed successfully"
    
    deactivate
}

# Install Git if needed
install_git() {
    if ! command -v git &> /dev/null; then
        print_info "Installing Git..."
        case $PKG_MANAGER in
            apt)
                $INSTALL_CMD git
                ;;
            yum|dnf)
                $INSTALL_CMD git
                ;;
            pacman)
                $INSTALL_CMD git
                ;;
        esac
    else
        print_info "Git is already installed"
    fi
}

# Create launcher script
create_launcher() {
    print_header "Creating launcher script"
    
    LAUNCHER="$INSTALL_DIR/start-opsechat.sh"
    
    cat > "$LAUNCHER" << 'EOF'
#!/bin/bash
# opsechat Launcher Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Error: Virtual environment not found at $VENV_DIR"
    echo "Please run the installer again: ./install.sh"
    exit 1
fi

echo "[*] Starting opsechat..."
echo "[*] Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "[*] Launching opsechat server..."
cd "$SCRIPT_DIR"
python runserver.py

deactivate
EOF
    
    chmod +x "$LAUNCHER"
    print_info "Launcher script created at: $LAUNCHER"
}

# Verify installation
verify_installation() {
    print_header "Verifying installation"
    
    local errors=0
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_info "✓ Python $PYTHON_VERSION"
    else
        print_error "✗ Python not found"
        errors=$((errors + 1))
    fi
    
    # Check Tor
    if command -v tor &> /dev/null; then
        TOR_VERSION=$(tor --version | head -n1 | awk '{print $3}')
        print_info "✓ Tor $TOR_VERSION"
    else
        print_error "✗ Tor not found"
        errors=$((errors + 1))
    fi
    
    # Check Tor service
    if command -v systemctl &> /dev/null; then
        if sudo systemctl is-active --quiet tor; then
            print_info "✓ Tor service is running"
        else
            print_warning "⚠ Tor service is not running"
        fi
    fi
    
    # Check virtual environment
    if [ -f "$VENV_DIR/bin/activate" ]; then
        print_info "✓ Virtual environment created"
    else
        print_error "✗ Virtual environment not found"
        errors=$((errors + 1))
    fi
    
    # Check Python packages
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        
        if python -c "import flask" 2>/dev/null; then
            print_info "✓ Flask installed"
        else
            print_error "✗ Flask not installed"
            errors=$((errors + 1))
        fi
        
        if python -c "import stem" 2>/dev/null; then
            print_info "✓ Stem installed"
        else
            print_error "✗ Stem not installed"
            errors=$((errors + 1))
        fi
        
        if python -c "import requests" 2>/dev/null; then
            print_info "✓ Requests installed"
        else
            print_error "✗ Requests not installed"
            errors=$((errors + 1))
        fi
        
        deactivate
    fi
    
    # Check repository
    if [ -f "$INSTALL_DIR/runserver.py" ]; then
        print_info "✓ opsechat repository"
    else
        print_error "✗ opsechat repository not found"
        errors=$((errors + 1))
    fi
    
    # Check launcher
    if [ -f "$INSTALL_DIR/start-opsechat.sh" ]; then
        print_info "✓ Launcher script"
    else
        print_error "✗ Launcher script not found"
        errors=$((errors + 1))
    fi
    
    echo ""
    if [ $errors -eq 0 ]; then
        print_info "All checks passed! ✓"
        return 0
    else
        print_error "$errors error(s) found during verification"
        return 1
    fi
}

# Print usage instructions
print_usage() {
    print_header "Installation Complete!"
    
    cat << EOF
opsechat has been installed successfully!

Installation directory: $INSTALL_DIR

To start opsechat:
    cd $INSTALL_DIR
    ./start-opsechat.sh

Or manually:
    cd $INSTALL_DIR
    source venv/bin/activate
    python runserver.py

Important Notes:
- The Tor service must be running for opsechat to work
- Check Tor status: sudo systemctl status tor
- Start Tor: sudo systemctl start tor
- The server will print an .onion URL to share with your chat participants
- Press Ctrl+C to stop the server

Documentation:
- README.md - General usage and features
- PGP_USAGE.md - PGP encryption guide
- EMAIL_SYSTEM.md - Email system documentation
- SECURITY.md - Security best practices

For help and support:
    https://github.com/HyperionGray/opsechat

EOF
}

# Main installation flow
main() {
    print_header "opsechat Installer"
    echo "This script will install opsechat and all dependencies"
    echo ""
    
    check_root
    check_sudo
    detect_os
    
    # Update package lists
    print_info "Updating package lists..."
    $UPDATE_CMD
    
    # Install components
    install_git
    install_python
    install_tor
    configure_tor
    setup_repository
    setup_virtualenv
    install_python_dependencies
    create_launcher
    
    # Verify and finish
    echo ""
    if verify_installation; then
        print_usage
        exit 0
    else
        print_error "Installation completed with errors. Please review the output above."
        exit 1
    fi
}

# Handle interruption
trap 'echo ""; print_error "Installation interrupted"; exit 1' INT TERM

# Run main function
main "$@"
