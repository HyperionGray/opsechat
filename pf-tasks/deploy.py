#!/usr/bin/env python3
"""
PF Task: Deploy opsechat using quadlets or compose
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

def detect_deployment_method():
    """Detect available deployment methods"""
    methods = {}
    
    # Check for systemd (quadlets)
    try:
        result = subprocess.run(['systemctl', '--version'], capture_output=True, check=True)
        methods['quadlet'] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        methods['quadlet'] = False
    
    # Check for compose tools
    for tool in ['podman-compose', 'docker-compose']:
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
            methods[tool] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            methods[tool] = False
    
    # Check for docker compose plugin
    try:
        subprocess.run(['docker', 'compose', 'version'], capture_output=True, check=True)
        methods['docker-compose-plugin'] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        methods['docker-compose-plugin'] = False
    
    return methods

def deploy_quadlet():
    """Deploy using systemd quadlets"""
    print("[*] Deploying with systemd quadlets")
    
    project_root = Path(__file__).parent.parent
    quadlet_dir = project_root / "quadlets"
    
    # Determine systemd directory
    user_systemd_dir = Path.home() / ".config" / "containers" / "systemd"
    system_systemd_dir = Path("/etc/containers/systemd")
    
    # Try user directory first
    target_dir = user_systemd_dir
    if not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            print("[*] Cannot create user systemd directory, trying system directory")
            target_dir = system_systemd_dir
    
    print(f"[*] Installing quadlet files to: {target_dir}")
    
    # Copy quadlet files
    quadlet_files = list(quadlet_dir.glob("*.container")) + list(quadlet_dir.glob("*.network")) + list(quadlet_dir.glob("*.timer")) + list(quadlet_dir.glob("*.service")) + list(quadlet_dir.glob("*.volume"))
    
    for file in quadlet_files:
        dest = target_dir / file.name
        print(f"[*] Copying {file.name}")
        try:
            shutil.copy2(file, dest)
        except PermissionError:
            print(f"[!] Permission denied copying to {dest}")
            print("[!] Try running with sudo or use user directory")
            return False
    
    # Copy torrc to user directory
    torrc_source = project_root / "torrc"
    torrc_dest = Path.home() / "opsechat" / "torrc"
    torrc_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(torrc_source, torrc_dest)
    print(f"[*] Copied torrc to {torrc_dest}")
    
    # Reload systemd
    print("[*] Reloading systemd daemon")
    run_command(['systemctl', '--user', 'daemon-reload'])
    
    # Enable and start services
    services = ['opsechat.network', 'opsechat-tor.service', 'opsechat-app.service']
    
    for service in services:
        print(f"[*] Enabling {service}")
        run_command(['systemctl', '--user', 'enable', service])
        
        print(f"[*] Starting {service}")
        run_command(['systemctl', '--user', 'start', service])
    
    # Enable cleanup timer
    print("[*] Enabling cleanup timer")
    run_command(['systemctl', '--user', 'enable', 'opsechat-cleanup.timer'])
    run_command(['systemctl', '--user', 'start', 'opsechat-cleanup.timer'])
    
    return True

def deploy_compose(compose_tool):
    """Deploy using docker-compose or podman-compose"""
    print(f"[*] Deploying with {compose_tool}")
    
    project_root = Path(__file__).parent.parent
    
    # Use existing compose scripts
    compose_up_script = project_root / "compose-up.sh"
    
    if compose_up_script.exists():
        print("[*] Using existing compose-up.sh script")
        run_command([str(compose_up_script)], cwd=project_root)
    else:
        # Fallback to direct compose command
        if compose_tool == 'docker-compose-plugin':
            cmd = ['docker', 'compose', 'up', '-d']
        else:
            cmd = [compose_tool, 'up', '-d']
        
        run_command(cmd, cwd=project_root)
    
    return True

def main():
    """Main deployment task"""
    parser = argparse.ArgumentParser(description='Deploy opsechat')
    parser.add_argument('--method', choices=['quadlet', 'compose', 'auto'], 
                       default='auto', help='Deployment method')
    parser.add_argument('--compose-tool', choices=['podman-compose', 'docker-compose', 'docker-compose-plugin'],
                       help='Specific compose tool to use')
    
    args = parser.parse_args()
    
    print("=== PF Task: Deploy ===")
    
    # Detect available methods
    methods = detect_deployment_method()
    print(f"[*] Available deployment methods: {methods}")
    
    success = False
    
    if args.method == 'quadlet' or (args.method == 'auto' and methods['quadlet']):
        success = deploy_quadlet()
    elif args.method == 'compose' or args.method == 'auto':
        # Choose compose tool
        if args.compose_tool and methods.get(args.compose_tool):
            success = deploy_compose(args.compose_tool)
        else:
            # Auto-detect compose tool
            for tool in ['podman-compose', 'docker-compose', 'docker-compose-plugin']:
                if methods.get(tool):
                    success = deploy_compose(tool)
                    break
    
    if success:
        print("[✓] Deployment completed successfully")
        print("[*] To view the onion address:")
        if methods['quadlet']:
            print("    systemctl --user status opsechat-app.service")
            print("    journalctl --user -u opsechat-app.service")
        else:
            print("    ./compose-up.sh")
            print("    docker-compose logs opsechat")
        sys.exit(0)
    else:
        print("[!] Deployment failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
