#!/bin/bash

# Security Scanning Script for opsechat
# Implements Amazon Q Code Review recommendations for automated security scanning

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/security-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create reports directory
mkdir -p "$REPORT_DIR"

echo -e "${BLUE}🔍 opsechat Security Scanner${NC}"
echo -e "${BLUE}================================${NC}"
echo "Timestamp: $(date)"
echo "Project Root: $PROJECT_ROOT"
echo ""

# Function to print section headers
print_section() {
    echo -e "\n${BLUE}📋 $1${NC}"
    echo "----------------------------------------"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install missing tools
install_security_tools() {
    print_section "Installing Security Tools"
    
    # Install pip-audit for Python dependency scanning
    if ! command_exists pip-audit; then
        echo "Installing pip-audit..."
        pip install pip-audit
    fi
    
    # Install safety for additional Python security checks
    if ! command_exists safety; then
        echo "Installing safety..."
        pip install safety
    fi
    
    # Install npm audit for Node.js dependencies
    if command_exists npm && [ -f "$PROJECT_ROOT/package.json" ]; then
        echo "npm is available for Node.js dependency scanning"
    fi
    
    # Install bandit for Python code security analysis
    if ! command_exists bandit; then
        echo "Installing bandit..."
        pip install bandit
    fi
    
    echo -e "${GREEN}✅ Security tools installation complete${NC}"
}

# Function to scan Python dependencies
scan_python_dependencies() {
    print_section "Python Dependency Vulnerability Scan"
    
    local report_file="$REPORT_DIR/python_deps_$TIMESTAMP.json"
    local summary_file="$REPORT_DIR/python_deps_summary_$TIMESTAMP.txt"
    
    cd "$PROJECT_ROOT"
    
    echo "Scanning Python dependencies with pip-audit..."
    if pip-audit --format=json --output="$report_file" 2>/dev/null; then
        echo -e "${GREEN}✅ No vulnerabilities found in Python dependencies${NC}"
        echo "No vulnerabilities found" > "$summary_file"
    else
        echo -e "${YELLOW}⚠️  Vulnerabilities found in Python dependencies${NC}"
        echo "Check report: $report_file"
        
        # Create human-readable summary
        pip-audit --format=text > "$summary_file" 2>/dev/null || true
    fi
    
    # Additional scan with safety
    echo "Running additional scan with safety..."
    local safety_report="$REPORT_DIR/safety_$TIMESTAMP.txt"
    if safety check --json > "$safety_report" 2>/dev/null; then
        echo -e "${GREEN}✅ Safety scan passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Safety scan found issues${NC}"
        echo "Check report: $safety_report"
    fi
}

# Function to scan Node.js dependencies
scan_nodejs_dependencies() {
    print_section "Node.js Dependency Vulnerability Scan"
    
    if [ ! -f "$PROJECT_ROOT/package.json" ]; then
        echo "No package.json found, skipping Node.js scan"
        return
    fi
    
    cd "$PROJECT_ROOT"
    local report_file="$REPORT_DIR/npm_audit_$TIMESTAMP.json"
    
    echo "Scanning Node.js dependencies with npm audit..."
    if npm audit --json > "$report_file" 2>/dev/null; then
        local vulnerabilities=$(jq '.metadata.vulnerabilities.total // 0' "$report_file" 2>/dev/null || echo "0")
        if [ "$vulnerabilities" -eq 0 ]; then
            echo -e "${GREEN}✅ No vulnerabilities found in Node.js dependencies${NC}"
        else
            echo -e "${YELLOW}⚠️  Found $vulnerabilities vulnerabilities in Node.js dependencies${NC}"
            echo "Check report: $report_file"
        fi
    else
        echo -e "${RED}❌ npm audit failed${NC}"
    fi
}

# Function to scan for hardcoded secrets
scan_secrets() {
    print_section "Hardcoded Secrets Scan"
    
    local report_file="$REPORT_DIR/secrets_scan_$TIMESTAMP.txt"
    
    echo "Scanning for potential hardcoded secrets..."
    
    # Define patterns to search for
    local patterns=(
        "password\s*=\s*['\"][^'\"]{3,}['\"]"
        "api_key\s*=\s*['\"][^'\"]{10,}['\"]"
        "secret\s*=\s*['\"][^'\"]{10,}['\"]"
        "token\s*=\s*['\"][^'\"]{10,}['\"]"
        "aws_access_key_id\s*=\s*['\"][^'\"]{10,}['\"]"
        "aws_secret_access_key\s*=\s*['\"][^'\"]{10,}['\"]"
        "-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"
    )
    
    local found_secrets=false
    
    for pattern in "${patterns[@]}"; do
        if grep -r -i -E "$pattern" "$PROJECT_ROOT" \
           --exclude-dir=.git \
           --exclude-dir=node_modules \
           --exclude-dir=venv \
           --exclude-dir=__pycache__ \
           --exclude-dir=security-reports \
           --exclude="*.pyc" \
           --exclude="security-scan.sh" >> "$report_file" 2>/dev/null; then
            found_secrets=true
        fi
    done
    
    if [ "$found_secrets" = true ]; then
        echo -e "${RED}❌ Potential hardcoded secrets found${NC}"
        echo "Check report: $report_file"
    else
        echo -e "${GREEN}✅ No hardcoded secrets detected${NC}"
        echo "No secrets found" > "$report_file"
    fi
}

# Function to run static code analysis
run_static_analysis() {
    print_section "Static Code Security Analysis"
    
    local report_file="$REPORT_DIR/bandit_$TIMESTAMP.json"
    local summary_file="$REPORT_DIR/bandit_summary_$TIMESTAMP.txt"
    
    cd "$PROJECT_ROOT"
    
    echo "Running bandit security analysis..."
    if bandit -r . -f json -o "$report_file" \
       --exclude ./venv,./node_modules,./.git,./security-reports \
       2>/dev/null; then
        echo -e "${GREEN}✅ Bandit analysis passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Bandit found potential security issues${NC}"
        echo "Check report: $report_file"
        
        # Create human-readable summary
        bandit -r . --exclude ./venv,./node_modules,./.git,./security-reports > "$summary_file" 2>/dev/null || true
    fi
}

# Function to generate summary report
generate_summary() {
    print_section "Security Scan Summary"
    
    local summary_file="$REPORT_DIR/security_summary_$TIMESTAMP.md"
    
    {
        echo "# opsechat Security Scan Summary"
        echo ""
        echo "**Scan Date:** $(date)"
        echo "**Project:** opsechat"
        echo "**Scanner Version:** 1.0.0"
        echo ""
        echo "## Scan Results"
        echo ""
        
        # Count reports
        local total_reports=$(find "$REPORT_DIR" -name "*_$TIMESTAMP.*" | wc -l)
        echo "- **Total Scans Performed:** $total_reports"
        
        # Check for any issues
        local issues_found=false
        
        if [ -f "$REPORT_DIR/python_deps_$TIMESTAMP.json" ]; then
            if [ -s "$REPORT_DIR/python_deps_$TIMESTAMP.json" ] && [ "$(cat "$REPORT_DIR/python_deps_$TIMESTAMP.json")" != "[]" ]; then
                echo "- **Python Dependencies:** ⚠️  Issues found"
                issues_found=true
            else
                echo "- **Python Dependencies:** ✅ Clean"
            fi
        fi
        
        if [ -f "$REPORT_DIR/secrets_scan_$TIMESTAMP.txt" ]; then
            if grep -q "No secrets found" "$REPORT_DIR/secrets_scan_$TIMESTAMP.txt"; then
                echo "- **Secrets Scan:** ✅ Clean"
            else
                echo "- **Secrets Scan:** ⚠️  Potential issues found"
                issues_found=true
            fi
        fi
        
        echo ""
        echo "## Recommendations"
        echo ""
        
        if [ "$issues_found" = true ]; then
            echo "1. Review detailed reports in the security-reports directory"
            echo "2. Address any identified vulnerabilities"
            echo "3. Update dependencies to latest secure versions"
            echo "4. Consider implementing automated security scanning in CI/CD"
        else
            echo "✅ No critical security issues identified"
            echo "1. Continue regular security scanning"
            echo "2. Keep dependencies updated"
            echo "3. Monitor for new vulnerabilities"
        fi
        
        echo ""
        echo "## Report Files"
        echo ""
        find "$REPORT_DIR" -name "*_$TIMESTAMP.*" -exec basename {} \; | sort | sed 's/^/- /'
        
    } > "$summary_file"
    
    echo -e "${GREEN}📊 Summary report generated: $summary_file${NC}"
}

# Main execution
main() {
    echo "Starting comprehensive security scan..."
    
    # Install required tools
    install_security_tools
    
    # Run all scans
    scan_python_dependencies
    scan_nodejs_dependencies
    scan_secrets
    run_static_analysis
    
    # Generate summary
    generate_summary
    
    echo ""
    echo -e "${GREEN}🎉 Security scan completed!${NC}"
    echo -e "Reports available in: ${BLUE}$REPORT_DIR${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Review the summary report"
    echo "2. Address any identified issues"
    echo "3. Schedule regular security scans"
    echo "4. Consider integrating into CI/CD pipeline"
}

# Run main function
main "$@"