#!/usr/bin/env python3
"""
PF Task: Test opsechat functionality
Compatible with pf-web-poly-compile-helper-runner patterns
"""

import subprocess
import sys
import os
import time
import requests
from pathlib import Path
import argparse

def run_command(cmd, cwd=None, check=True):
    """Run command with proper error handling"""
    print(f"[*] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        print(f"[!] Command failed: {e}")
        if e.stderr:
            print(f"[!] Error: {e.stderr}")
        if check:
            sys.exit(1)
        return e

def test_container_health():
    """Test container health and status"""
    print("[*] Testing container health")
    
    # Check if containers are running
    containers = ['opsechat-tor', 'opsechat-app']
    
    for container in containers:
        print(f"[*] Checking {container}")
        
        # Try podman first, then docker
        for tool in ['podman', 'docker']:
            try:
                result = run_command([tool, 'ps', '--filter', f'name={container}'], check=False)
                if result.returncode == 0 and container in result.stdout:
                    print(f"[✓] {container} is running ({tool})")
                    break
            except:
                continue
        else:
            print(f"[!] {container} not found or not running")
            return False
    
    return True

def test_systemd_services():
    """Test systemd service status"""
    print("[*] Testing systemd services")
    
    services = ['opsechat-network.service', 'opsechat-tor.service', 'opsechat-app.service']
    
    for service in services:
        print(f"[*] Checking {service}")
        result = run_command(['systemctl', '--user', 'is-active', service], check=False)
        
        if result.returncode == 0 and 'active' in result.stdout:
            print(f"[✓] {service} is active")
        else:
            print(f"[!] {service} is not active")
            # Show status for debugging
            run_command(['systemctl', '--user', 'status', service], check=False)
            return False
    
    return True

def test_tor_connectivity():
    """Test Tor connectivity and hidden service"""
    print("[*] Testing Tor connectivity")
    
    # Check if we can get the onion address from logs
    onion_address = None
    
    # Try to get onion address from container logs
    for tool in ['podman', 'docker']:
        try:
            result = run_command([tool, 'logs', 'opsechat-app'], check=False)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Your service is available at:' in line:
                        # Extract onion address
                        parts = line.split('Your service is available at:')
                        if len(parts) > 1:
                            onion_address = parts[1].strip()
                            print(f"[✓] Found onion address: {onion_address}")
                            break
                break
        except:
            continue
    
    if not onion_address:
        print("[!] Could not find onion address in logs")
        return False
    
    return True

def test_python_modules():
    """Test Python module imports"""
    print("[*] Testing Python module imports")
    
    project_root = Path(__file__).parent.parent
    
    # Test importing main modules
    modules = [
        'runserver',
        'email_system', 
        'email_transport',
        'domain_manager',
        'email_security_tools'
    ]
    
    for module in modules:
        print(f"[*] Testing import of {module}")
        
        # Test in container if available
        for tool in ['podman', 'docker']:
            try:
                cmd = [tool, 'exec', 'opsechat-app', 'python', '-c', f'import {module}; print("OK")']
                result = run_command(cmd, check=False)
                
                if result.returncode == 0 and 'OK' in result.stdout:
                    print(f"[✓] {module} imports successfully")
                    break
            except:
                continue
        else:
            print(f"[!] Failed to test {module} import")
            return False
    
    return True

def test_playwright_e2e():
    """Run Playwright end-to-end tests if available"""
    print("[*] Testing with Playwright (if available)")
    
    project_root = Path(__file__).parent.parent
    
    # Check if npm and playwright are available
    try:
        run_command(['npm', '--version'], check=True)
        
        # Check if node_modules exists
        if (project_root / 'node_modules').exists():
            print("[*] Running Playwright tests")
            result = run_command(['npm', 'run', 'test:headless'], cwd=project_root, check=False)
            
            if result.returncode == 0:
                print("[✓] Playwright tests passed")
                return True
            else:
                print("[!] Playwright tests failed")
                return False
        else:
            print("[*] Playwright not installed, skipping E2E tests")
            return True
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[*] npm not available, skipping Playwright tests")
        return True

def main():
    """Main test task"""
    parser = argparse.ArgumentParser(description='Test opsechat deployment')
    parser.add_argument('--method', choices=['container', 'systemd', 'all'], 
                       default='all', help='Test method')
    parser.add_argument('--skip-e2e', action='store_true', help='Skip end-to-end tests')
    
    args = parser.parse_args()
    
    print("=== PF Task: Test ===")
    
    tests_passed = 0
    total_tests = 0
    
    if args.method in ['container', 'all']:
        total_tests += 1
        if test_container_health():
            tests_passed += 1
    
    if args.method in ['systemd', 'all']:
        total_tests += 1
        if test_systemd_services():
            tests_passed += 1
    
    if args.method in ['all']:
        total_tests += 1
        if test_tor_connectivity():
            tests_passed += 1
        
        total_tests += 1
        if test_python_modules():
            tests_passed += 1
        
        if not args.skip_e2e:
            total_tests += 1
            if test_playwright_e2e():
                tests_passed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("[✓] All tests passed")
        sys.exit(0)
    else:
        print("[!] Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()