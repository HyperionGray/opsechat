#!/bin/bash

# Amazon Q Developer CLI Setup Script for opsechat
# This script prepares the environment for Amazon Q integration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root for security reasons"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
        log_error "Python 3.8+ is required, found $PYTHON_VERSION"
        exit 1
    fi
    log_success "Python $PYTHON_VERSION found"
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is required but not installed"
        exit 1
    fi
    log_success "pip3 found"
    
    # Check curl
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
    log_success "curl found"
}

# Install AWS CLI v2
install_aws_cli() {
    log_info "Checking AWS CLI installation..."
    
    if command -v aws &> /dev/null; then
        AWS_VERSION=$(aws --version 2>&1 | cut -d/ -f2 | cut -d' ' -f1)
        if [[ $AWS_VERSION == 2.* ]]; then
            log_success "AWS CLI v2 already installed: $AWS_VERSION"
            return 0
        else
            log_warning "AWS CLI v1 found, upgrading to v2..."
        fi
    fi
    
    log_info "Installing AWS CLI v2..."
    
    # Detect architecture
    ARCH=$(uname -m)
    if [[ "$ARCH" == "x86_64" ]]; then
        AWS_CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
    elif [[ "$ARCH" == "aarch64" ]]; then
        AWS_CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"
    else
        log_error "Unsupported architecture: $ARCH"
        exit 1
    fi
    
    # Download and install
    cd /tmp
    curl -s "$AWS_CLI_URL" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    
    # Install to user directory if no sudo access
    if sudo -n true 2>/dev/null; then
        sudo ./aws/install
    else
        log_warning "No sudo access, installing to ~/.local/bin"
        ./aws/install --install-dir ~/.local/aws-cli --bin-dir ~/.local/bin
        export PATH="$HOME/.local/bin:$PATH"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    fi
    
    # Cleanup
    rm -rf awscliv2.zip aws/
    
    log_success "AWS CLI v2 installed successfully"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies for AWS integration..."
    
    cd "$PROJECT_ROOT"
    
    # Install AWS SDK dependencies
    pip3 install --user boto3 botocore
    
    # Install security scanning tools
    pip3 install --user safety bandit semgrep
    
    log_success "Python dependencies installed"
}

# Setup AWS configuration
setup_aws_config() {
    log_info "Setting up AWS configuration..."
    
    AWS_DIR="$HOME/.aws"
    mkdir -p "$AWS_DIR"
    
    # Create credentials template if not exists
    if [[ ! -f "$AWS_DIR/credentials" ]]; then
        log_info "Creating AWS credentials template..."
        cat > "$AWS_DIR/credentials" << 'EOF'
# AWS Credentials for Amazon Q Integration
# Replace with your actual credentials

[default]
# aws_access_key_id = YOUR_ACCESS_KEY_ID
# aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

[amazon-q]
# aws_access_key_id = YOUR_Q_SPECIFIC_ACCESS_KEY
# aws_secret_access_key = YOUR_Q_SPECIFIC_SECRET_KEY
EOF
        log_warning "AWS credentials template created at $AWS_DIR/credentials"
        log_warning "Please edit this file with your actual AWS credentials"
    fi
    
    # Create config template if not exists
    if [[ ! -f "$AWS_DIR/config" ]]; then
        log_info "Creating AWS config template..."
        cat > "$AWS_DIR/config" << 'EOF'
[default]
region = us-east-1
output = json

[profile amazon-q]
region = us-east-1
output = json
EOF
        log_success "AWS config template created at $AWS_DIR/config"
    fi
}

# Setup environment variables
setup_environment() {
    log_info "Setting up environment variables..."
    
    ENV_FILE="$PROJECT_ROOT/.env"
    
    if [[ ! -f "$ENV_FILE" ]]; then
        log_info "Creating .env file for opsechat..."
        cat > "$ENV_FILE" << 'EOF'
# opsechat Environment Configuration

# Tor Configuration
TOR_CONTROL_HOST=127.0.0.1
TOR_CONTROL_PORT=9051

# AWS Integration (Optional)
ENABLE_AWS_INTEGRATION=false
AMAZON_Q_ENABLED=false
AMAZON_Q_PROFILE=amazon-q
AMAZON_Q_REGION=us-east-1
CODEWHISPERER_ENABLED=false

# Security Settings
SECURITY_SCAN_ENABLED=true
DEPENDENCY_CHECK_ENABLED=true

# Development Settings
DEBUG=false
FLASK_ENV=production
EOF
        log_success ".env file created"
    else
        log_info ".env file already exists, skipping creation"
    fi
}

# Setup Amazon Q rules
setup_amazon_q_rules() {
    log_info "Verifying Amazon Q rules configuration..."
    
    if [[ -f "$PROJECT_ROOT/amazon-q-rules.json" ]]; then
        log_success "Amazon Q rules configuration found"
    else
        log_error "Amazon Q rules configuration not found"
        log_error "Please ensure amazon-q-rules.json exists in the project root"
        exit 1
    fi
}

# Test AWS configuration
test_aws_config() {
    log_info "Testing AWS configuration..."
    
    if command -v aws &> /dev/null; then
        # Test AWS CLI
        if aws sts get-caller-identity &> /dev/null; then
            log_success "AWS credentials are configured and valid"
        else
            log_warning "AWS credentials not configured or invalid"
            log_warning "Run 'aws configure' to set up your credentials"
        fi
    else
        log_error "AWS CLI not found in PATH"
        exit 1
    fi
}

# Setup GitHub Actions integration
setup_github_actions() {
    log_info "Verifying GitHub Actions integration..."
    
    WORKFLOW_FILE="$PROJECT_ROOT/.github/workflows/amazon-q-security-scan.yml"
    
    if [[ -f "$WORKFLOW_FILE" ]]; then
        log_success "GitHub Actions workflow found"
        log_info "To enable AWS integration in GitHub Actions:"
        log_info "1. Go to your repository settings"
        log_info "2. Navigate to Secrets and variables > Actions"
        log_info "3. Add the following secrets:"
        log_info "   - AWS_ACCESS_KEY_ID"
        log_info "   - AWS_SECRET_ACCESS_KEY"
    else
        log_error "GitHub Actions workflow not found"
        log_error "Please ensure .github/workflows/amazon-q-security-scan.yml exists"
    fi
}

# Create setup verification script
create_verification_script() {
    log_info "Creating verification script..."
    
    cat > "$PROJECT_ROOT/verify-amazon-q-setup.sh" << 'EOF'
#!/bin/bash

# Amazon Q Setup Verification Script

echo "=== Amazon Q Integration Verification ==="
echo

# Check AWS CLI
echo "1. AWS CLI:"
if command -v aws &> /dev/null; then
    echo "   ✅ AWS CLI installed: $(aws --version)"
else
    echo "   ❌ AWS CLI not found"
fi

# Check AWS credentials
echo "2. AWS Credentials:"
if aws sts get-caller-identity &> /dev/null; then
    echo "   ✅ AWS credentials configured"
else
    echo "   ❌ AWS credentials not configured or invalid"
fi

# Check Python dependencies
echo "3. Python Dependencies:"
for pkg in boto3 botocore safety bandit; do
    if python3 -c "import $pkg" &> /dev/null; then
        echo "   ✅ $pkg installed"
    else
        echo "   ❌ $pkg not installed"
    fi
done

# Check configuration files
echo "4. Configuration Files:"
for file in .env amazon-q-rules.json .github/workflows/amazon-q-security-scan.yml; do
    if [[ -f "$file" ]]; then
        echo "   ✅ $file exists"
    else
        echo "   ❌ $file missing"
    fi
done

# Check environment variables
echo "5. Environment Variables:"
source .env 2>/dev/null || true
if [[ "$ENABLE_AWS_INTEGRATION" == "true" ]]; then
    echo "   ✅ AWS integration enabled"
else
    echo "   ⚠️  AWS integration disabled (set ENABLE_AWS_INTEGRATION=true to enable)"
fi

echo
echo "=== Setup Complete ==="
echo "To enable Amazon Q integration:"
echo "1. Configure AWS credentials: aws configure"
echo "2. Edit .env file: set ENABLE_AWS_INTEGRATION=true"
echo "3. Add GitHub secrets for CI/CD integration"
echo "4. Wait for Amazon Q Developer CLI public release"
EOF

    chmod +x "$PROJECT_ROOT/verify-amazon-q-setup.sh"
    log_success "Verification script created: verify-amazon-q-setup.sh"
}

# Main setup function
main() {
    echo "=== Amazon Q Developer CLI Setup for opsechat ==="
    echo
    
    check_root
    check_prerequisites
    install_aws_cli
    install_python_deps
    setup_aws_config
    setup_environment
    setup_amazon_q_rules
    test_aws_config
    setup_github_actions
    create_verification_script
    
    echo
    log_success "Amazon Q setup completed successfully!"
    echo
    log_info "Next steps:"
    log_info "1. Configure your AWS credentials: aws configure"
    log_info "2. Edit .env file to enable AWS integration"
    log_info "3. Run verification: ./verify-amazon-q-setup.sh"
    log_info "4. See AMAZON_Q_SETUP.md for detailed configuration"
    echo
    log_warning "Note: Amazon Q Developer CLI is not yet publicly available"
    log_warning "This setup prepares your environment for future integration"
}

# Run main function
main "$@"