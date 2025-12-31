#!/usr/bin/env python3
"""
Simple test to check pf task imports and basic functionality
"""

import sys
import os
from pathlib import Path

# Add pf-tasks to path
sys.path.insert(0, str(Path(__file__).parent / "pf-tasks"))

def test_basic_imports():
    """Test basic imports of all pf task modules"""
    print("Testing basic imports...")
    
    modules = ['build', 'deploy', 'test', 'clean']
    results = {}
    
    for module_name in modules:
        try:
            module = __import__(module_name)
            print(f"[✓] Successfully imported {module_name}")
            results[module_name] = True
            
            # Check for main functions
            if hasattr(module, 'main'):
                print(f"[✓] {module_name} has main() function")
            else:
                print(f"[!] {module_name} missing main() function")
                
            # Check for run_command function
            if hasattr(module, 'run_command'):
                print(f"[✓] {module_name} has run_command() function")
            else:
                print(f"[!] {module_name} missing run_command() function")
                
        except Exception as e:
            print(f"[!] Failed to import {module_name}: {e}")
            results[module_name] = False
    
    return results

def test_file_structure():
    """Test that all expected files exist"""
    print("\nTesting file structure...")
    
    project_root = Path(__file__).parent
    
    # Check pf-tasks directory
    pf_tasks_dir = project_root / "pf-tasks"
    if pf_tasks_dir.exists():
        print(f"[✓] pf-tasks directory exists")
    else:
        print(f"[!] pf-tasks directory missing")
        return False
    
    # Check individual pf task files
    expected_files = ['build.py', 'deploy.py', 'test.py', 'clean.py', 'README.md']
    for filename in expected_files:
        file_path = pf_tasks_dir / filename
        if file_path.exists():
            print(f"[✓] {filename} exists")
        else:
            print(f"[!] {filename} missing")
    
    # Check integration files
    integration_files = ['docker-compose.yml', 'compose-up.sh', 'compose-down.sh']
    for filename in integration_files:
        file_path = project_root / filename
        if file_path.exists():
            print(f"[✓] Integration file {filename} exists")
        else:
            print(f"[!] Integration file {filename} missing")
    
    return True

def main():
    print("=== Simple PF Task Test ===")
    
    # Test file structure first
    structure_ok = test_file_structure()
    if not structure_ok:
        print("File structure issues found!")
        return False
    
    # Test imports
    import_results = test_basic_imports()
    
    # Summary
    total_modules = len(import_results)
    successful_imports = sum(import_results.values())
    
    print(f"\n=== Summary ===")
    print(f"Modules tested: {total_modules}")
    print(f"Successful imports: {successful_imports}")
    print(f"Failed imports: {total_modules - successful_imports}")
    
    if successful_imports == total_modules:
        print("[✓] All basic tests passed!")
        return True
    else:
        print("[!] Some tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)