#!/usr/bin/env python3
"""
Product Release Manual Testing Script

This script helps validate all the requirements for the OpSechat product release.
Run this to manually test all features before release.
"""

import sys
import os
import subprocess
import time
from pathlib import Path

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")

def test_tui_server():
    """Test TUI server startup"""
    print_section("Testing TUI Server")
    
    print("1. Testing TUI server help...")
    result = subprocess.run(['python3', 'tui-server.py', '--help'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print("✓ TUI server help works")
    else:
        print("✗ TUI server help failed")
        return False
    
    print("\n2. Testing TUI server startup (test mode, 5 seconds)...")
    print("   Starting server on port 5557...")
    proc = subprocess.Popen(['python3', 'tui-server.py', '--test', '--port', '5557'],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2)
    
    # Check if process is still running
    if proc.poll() is None:
        print("✓ TUI server started successfully")
        proc.terminate()
        proc.wait()
        return True
    else:
        stdout, stderr = proc.communicate()
        print(f"✗ TUI server failed to start")
        print(f"  stdout: {stdout}")
        print(f"  stderr: {stderr}")
        return False

def test_username_generation():
    """Test randomized username generation"""
    print_section("Testing Randomized Usernames")
    
    test_code = """
import sys
sys.path.insert(0, 'src')
from tui.server import ChatServer
server = ChatServer()
usernames = [server.generate_username() for _ in range(5)]
print('Generated usernames:')
for u in usernames:
    print(f'  - {u}')
print(f'\\nAll different: {len(set(usernames)) == 5}')
"""
    
    result = subprocess.run(['python3', '-c', test_code],
                          capture_output=True, text=True)
    
    if result.returncode == 0 and 'All different: True' in result.stdout:
        print(result.stdout)
        print("✓ Username generation works correctly")
        return True
    else:
        print("✗ Username generation failed")
        print(result.stdout)
        print(result.stderr)
        return False

def test_message_lifetime():
    """Test message burn lifetime"""
    print_section("Testing Message Lifetime (4-minute burn)")
    
    test_code = """
import sys
sys.path.insert(0, 'src')
from tui.server import ChatServer
server = ChatServer()
print(f'Message lifetime: {server.MESSAGE_LIFETIME} seconds')
print(f'Expected: 240 seconds (4 minutes)')
print(f'Correct: {server.MESSAGE_LIFETIME == 240}')
"""
    
    result = subprocess.run(['python3', '-c', test_code],
                          capture_output=True, text=True)
    
    if result.returncode == 0 and 'Correct: True' in result.stdout:
        print(result.stdout)
        print("✓ Message lifetime is correct (4 minutes)")
        return True
    else:
        print("✗ Message lifetime test failed")
        print(result.stdout)
        print(result.stderr)
        return False

def test_domain_manager():
    """Test domain manager import"""
    print_section("Testing Domain Manager")
    
    test_code = """
import domain_manager
print('Domain manager classes:')
print(f'  - DomainAPIClient: {hasattr(domain_manager, "DomainAPIClient")}')
print(f'  - PorkbunAPIClient: {hasattr(domain_manager, "PorkbunAPIClient")}')
client = domain_manager.PorkbunAPIClient('test_key', 'test_secret')
print(f'\\n✓ Domain manager imported and instantiated successfully')
"""
    
    result = subprocess.run(['python3', '-c', test_code],
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print(result.stdout)
        return True
    else:
        print("✗ Domain manager test failed")
        print(result.stderr)
        return False

def test_email_system():
    """Test email system import"""
    print_section("Testing Email System")
    
    test_code = """
import email_system
print('Email system classes:')
print(f'  - EmailStorage: {hasattr(email_system, "EmailStorage")}')
print(f'  - EmailValidator: {hasattr(email_system, "EmailValidator")}')
storage = email_system.EmailStorage()
print(f'\\n✓ Email system imported successfully')
"""
    
    result = subprocess.run(['python3', '-c', test_code],
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print(result.stdout)
        return True
    else:
        print("✗ Email system test failed")
        print(result.stderr)
        return False

def check_documentation():
    """Check documentation files"""
    print_section("Checking Documentation")
    
    docs = [
        ('README.md', 'Main README'),
        ('QUICKSTART.md', 'Quick Start Guide'),
        ('TUI_README.md', 'TUI Documentation'),
        ('SECURITY.md', 'Security Documentation'),
        ('docs/user-guide/PGP_USAGE.md', 'PGP Usage Guide'),
        ('docs/user-guide/EMAIL_SYSTEM.md', 'Email System Guide'),
    ]
    
    all_exist = True
    for filepath, name in docs:
        path = Path(filepath)
        if path.exists():
            size = path.stat().st_size
            print(f"✓ {name}: {filepath} ({size} bytes)")
        else:
            print(f"✗ {name}: {filepath} (MISSING)")
            all_exist = False
    
    return all_exist

def run_playwright_tests():
    """Run Playwright tests"""
    print_section("Running Playwright Tests")
    
    print("Running product release test suite...")
    result = subprocess.run(['npx', 'playwright', 'test', 
                           '--config=playwright-release.config.js',
                           '--reporter=line'],
                          capture_output=True, text=True)
    
    # Show last 30 lines of output
    lines = result.stdout.split('\n')
    for line in lines[-30:]:
        print(line)
    
    if 'passed' in result.stdout.lower() and result.returncode == 0:
        print("\n✓ Playwright tests passed")
        return True
    else:
        print("\n✗ Playwright tests failed")
        return False

def main():
    """Run all manual tests"""
    print("\n" + "="*60)
    print("  OpSecChat Product Release Manual Testing")
    print("="*60)
    
    os.chdir(Path(__file__).resolve().parents[2])
    
    tests = [
        ("Documentation Check", check_documentation),
        ("TUI Server", test_tui_server),
        ("Username Generation", test_username_generation),
        ("Message Lifetime", test_message_lifetime),
        ("Domain Manager", test_domain_manager),
        ("Email System", test_email_system),
        ("Playwright Tests", run_playwright_tests),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} raised exception: {e}")
            results.append((name, False))
    
    # Summary
    print_section("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready for release.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review and fix issues.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
