#!/usr/bin/env python3
"""
Development Environment Check
Verifies that all required dependencies are installed and accessible.
"""

import sys
import subprocess
import os

def check_command(cmd, name):
    """Check if a command is available"""
    try:
        subprocess.run([cmd, '--version'], capture_output=True, check=True)
        print(f"✓ {name} is installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"✗ {name} is NOT installed")
        return False

def check_python_module(module, name):
    """Check if a Python module can be imported"""
    try:
        __import__(module)
        print(f"✓ {name} is installed")
        return True
    except ImportError:
        print(f"✗ {name} is NOT installed")
        return False

def check_file(filepath, name):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✓ {name} exists")
        return True
    else:
        print(f"✗ {name} is missing")
        return False

def main():
    print("=" * 60)
    print("OpSecChat Development Environment Check")
    print("=" * 60)
    print()
    
    all_good = True
    
    # Check Python version
    print("Python Version Check:")
    if sys.version_info >= (3, 8):
        print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} (>= 3.8 required)")
    else:
        print(f"✗ Python {sys.version_info.major}.{sys.version_info.minor} (3.8+ required)")
        all_good = False
    print()
    
    # Check system commands
    print("System Commands:")
    all_good &= check_command('git', 'Git')
    all_good &= check_command('node', 'Node.js')
    all_good &= check_command('npm', 'npm')
    check_command('podman', 'Podman')  # Optional
    check_command('docker', 'Docker')  # Optional
    print()
    
    # Check Python modules
    print("Python Modules:")
    all_good &= check_python_module('flask', 'Flask')
    all_good &= check_python_module('stem', 'Stem (Tor)')
    check_python_module('pytest', 'pytest')  # Dev dependency
    print()
    
    # Check important files
    print("Configuration Files:")
    check_file('requirements.txt', 'requirements.txt')
    check_file('requirements-dev.txt', 'requirements-dev.txt')
    check_file('package.json', 'package.json')
    check_file('pytest.ini', 'pytest.ini')
    check_file('VERSION', 'VERSION')
    print()
    
    # Check Node modules
    print("Node.js Environment:")
    if os.path.exists('node_modules'):
        print("✓ node_modules exists")
        if os.path.exists('node_modules/.bin/playwright'):
            print("✓ Playwright is installed")
        else:
            print("✗ Playwright is NOT installed (run: npx playwright install)")
            all_good = False
    else:
        print("✗ node_modules missing (run: npm install)")
        all_good = False
    print()
    
    # Summary
    print("=" * 60)
    if all_good:
        print("✅ All required dependencies are installed!")
        print()
        print("You're ready to develop! Try:")
        print("  python runserver.py")
        print("  npm test")
    else:
        print("⚠️  Some dependencies are missing.")
        print()
        print("To install missing dependencies:")
        print("  pip install -r requirements.txt")
        print("  pip install -r requirements-dev.txt")
        print("  npm install")
        print("  npx playwright install")
    print("=" * 60)
    
    return 0 if all_good else 1

if __name__ == '__main__':
    sys.exit(main())
