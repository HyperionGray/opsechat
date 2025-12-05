#!/usr/bin/env python3
"""
PF Task: Clean up opsechat deployment and resources
Compatible with pf-web-poly-compile-helper-runner patterns
"""

import subprocess
import sys
import os
import shutil
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

def clean_systemd_services():
    """Clean up systemd services and quadlets"""
    print("[*] Cleaning systemd services")
    
    services = [
        'opsechat-cleanup.timer',
        'opsechat-cleanup.service', 
        'opsechat-app.service',
        'opsechat-tor.service',
        'opsechat-network.service'
    ]
    
    for service in services:
        print(f"[*] Stopping {service}")
        run_command(['systemctl', '--user', 'stop', service], check=False)
        
        print(f"[*] Disabling {service}")
        run_command(['systemctl', '--user', 'disable', service], check=False)
    
    # Remove quadlet files
    user_systemd_dir = Path.home() / ".config" / "containers" / "systemd"
    system_systemd_dir = Path("/etc/containers/systemd")
    
    quadlet_files = [
        'opsechat-tor.container',
        'opsechat-app.container', 
        'opsechat-network.network',
        'opsechat-cleanup.timer',
        'opsechat-cleanup.service'
    ]
    
    for systemd_dir in [user_systemd_dir, system_systemd_dir]:
        if systemd_dir.exists():
            for file in quadlet_files:
                file_path = systemd_dir / file
                if file_path.exists():
                    print(f"[*] Removing {file_path}")
                    try:
                        file_path.unlink()
                    except PermissionError:
                        print(f"[!] Permission denied removing {file_path}")
    
    # Reload systemd
    print("[*] Reloading systemd daemon")
    run_command(['systemctl', '--user', 'daemon-reload'], check=False)
    
    return True

def clean_containers():
    """Clean up containers and images"""
    print("[*] Cleaning containers")
    
    containers = ['opsechat-app', 'opsechat-tor']
    
    for tool in ['podman', 'docker']:
        try:
            # Stop containers
            for container in containers:
                print(f"[*] Stopping {container} ({tool})")
                run_command([tool, 'stop', container], check=False)
                
                print(f"[*] Removing {container} ({tool})")
                run_command([tool, 'rm', container], check=False)
            
            # Remove network
            print(f"[*] Removing opsechat-network ({tool})")
            run_command([tool, 'network', 'rm', 'opsechat-network'], check=False)
            
            # Remove volumes
            print(f"[*] Removing volumes ({tool})")
            run_command([tool, 'volume', 'rm', 'opsechat_tor-data'], check=False)
            run_command([tool, 'volume', 'rm', 'opsechat-tor-data'], check=False)
            
            break  # If one tool works, don't try the other
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    return True

def clean_compose():
    """Clean up using compose tools"""
    print("[*] Cleaning with compose tools")
    
    project_root = Path(__file__).parent.parent
    
    # Try compose-down.sh script first
    compose_down_script = project_root / "compose-down.sh"
    if compose_down_script.exists():
        print("[*] Using compose-down.sh script")
        run_command([str(compose_down_script)], cwd=project_root, check=False)
    
    # Try compose tools directly
    for tool in ['podman-compose', 'docker-compose']:
        try:
            print(f"[*] Cleaning with {tool}")
            run_command([tool, 'down', '-v'], cwd=project_root, check=False)
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    # Try docker compose plugin
    try:
        print("[*] Cleaning with docker compose plugin")
        run_command(['docker', 'compose', 'down', '-v'], cwd=project_root, check=False)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return True

def clean_images(force=False):
    """Clean up container images"""
    print("[*] Cleaning container images")
    
    images = ['localhost/opsechat:latest', 'opsechat_opsechat', 'opsechat-opsechat']
    
    for tool in ['podman', 'docker']:
        try:
            for image in images:
                print(f"[*] Removing image {image} ({tool})")
                cmd = [tool, 'rmi', image]
                if force:
                    cmd.append('-f')
                run_command(cmd, check=False)
            
            break  # If one tool works, don't try the other
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    return True

def clean_build_artifacts():
    """Clean up build artifacts and cache"""
    print("[*] Cleaning build artifacts")
    
    project_root = Path(__file__).parent.parent
    
    # Remove Python cache
    for cache_dir in project_root.rglob('__pycache__'):
        if cache_dir.is_dir():
            print(f"[*] Removing {cache_dir}")
            shutil.rmtree(cache_dir, ignore_errors=True)
    
    # Remove .pyc files
    for pyc_file in project_root.rglob('*.pyc'):
        print(f"[*] Removing {pyc_file}")
        pyc_file.unlink(missing_ok=True)
    
    # Remove test artifacts
    test_dirs = ['test-results', 'playwright-report', '.pytest_cache']
    for test_dir in test_dirs:
        test_path = project_root / test_dir
        if test_path.exists():
            print(f"[*] Removing {test_path}")
            shutil.rmtree(test_path, ignore_errors=True)
    
    return True

def main():
    """Main cleanup task"""
    parser = argparse.ArgumentParser(description='Clean up opsechat deployment')
    parser.add_argument('--method', choices=['systemd', 'compose', 'containers', 'all'], 
                       default='all', help='Cleanup method')
    parser.add_argument('--images', action='store_true', help='Also remove container images')
    parser.add_argument('--force', action='store_true', help='Force removal of images')
    parser.add_argument('--artifacts', action='store_true', help='Clean build artifacts')
    
    args = parser.parse_args()
    
    print("=== PF Task: Clean ===")
    
    success = True
    
    if args.method in ['systemd', 'all']:
        success &= clean_systemd_services()
    
    if args.method in ['compose', 'all']:
        success &= clean_compose()
    
    if args.method in ['containers', 'all']:
        success &= clean_containers()
    
    if args.images or args.method == 'all':
        success &= clean_images(force=args.force)
    
    if args.artifacts or args.method == 'all':
        success &= clean_build_artifacts()
    
    if success:
        print("[✓] Cleanup completed successfully")
        sys.exit(0)
    else:
        print("[!] Some cleanup operations failed")
        sys.exit(1)

if __name__ == "__main__":
    main()