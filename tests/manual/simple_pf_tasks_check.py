#!/usr/bin/env python3
"""
Simple test to check pf task imports and basic functionality
"""

import sys
import os
from pathlib import Path

# Add pf-tasks to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "pf-tasks"))

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
    
    project_root = PROJECT_ROOT
    
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
    integration_files = ['container-compose.yml', 'compose-up.sh', 'compose-down.sh']
    for filename in integration_files:
        file_path = project_root / filename
        if file_path.exists():
            print(f"[✓] Integration file {filename} exists")
        else:
            print(f"[!] Integration file {filename} missing")
    
    return True

def test_clean_task_repo_flags():
    """Test clean.py repository-hygiene flags and behavior."""
    print("\nTesting clean.py repo flags...")
    import clean

    class Args:
        def __init__(self, method=None, images=False, artifacts=False, repo=False, repo_dry_run=False):
            self.method = method
            self.images = images
            self.artifacts = artifacts
            self.repo = repo
            self.repo_dry_run = repo_dry_run

    # Repo-only cleanup should skip deployment cleanup methods
    repo_only = Args(repo=True)
    if clean.determine_cleanup_method(repo_only) is None:
        print("[✓] clean.py repo-only mode skips deployment cleanup")
    else:
        print("[!] clean.py repo-only mode should skip deployment cleanup")
        return False

    # Default behavior should still run all cleanup stages
    default_args = Args()
    if clean.determine_cleanup_method(default_args) == 'all':
        print("[✓] clean.py default cleanup mode remains 'all'")
    else:
        print("[!] clean.py default cleanup mode should be 'all'")
        return False

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
    repo_flags_ok = test_clean_task_repo_flags()
    
    # Summary
    total_modules = len(import_results)
    successful_imports = sum(import_results.values())
    
    print(f"\n=== Summary ===")
    print(f"Modules tested: {total_modules}")
    print(f"Successful imports: {successful_imports}")
    print(f"Failed imports: {total_modules - successful_imports}")
    
    if successful_imports == total_modules and repo_flags_ok:
        print("[✓] All basic tests passed!")
        return True
    else:
        print("[!] Some tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
