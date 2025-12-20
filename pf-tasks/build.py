#!/usr/bin/env python3
"""
PF Task: Build opsechat container images
Compatible with pf-web-poly-compile-helper-runner patterns
"""

import subprocess
import sys
import os
from pathlib import Path

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

def detect_container_tool():
    """Detect available container build tool"""
    for tool in ['podman', 'docker']:
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
            return tool
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    print("[!] No container tool (podman/docker) found")
    sys.exit(1)

def build_image(container_tool, tag="localhost/opsechat:latest"):
    """Build the opsechat container image"""
    project_root = Path(__file__).parent.parent
    
    print(f"[*] Building opsechat image with {container_tool}")
    print(f"[*] Project root: {project_root}")
    print(f"[*] Target tag: {tag}")
    
    # Build the image (default to host networking to keep apt/SSL happy in CI)
    cmd = [container_tool, 'build', '-t', tag, '.']
    if container_tool == 'podman':
        # Podman host network and runc runtime avoid crun/socket DNS issues
        cmd = [container_tool, 'build', '--network', 'host', '--runtime', 'runc', '-t', tag, '.']
    elif container_tool == 'docker':
        # Host network is safe on Linux; noop on macOS/Windows but tolerated
        cmd = [container_tool, 'build', '--network', 'host', '-t', tag, '.']

    result = run_command(cmd, cwd=project_root)
    
    if result.returncode == 0:
        print(f"[✓] Successfully built {tag}")
        
        # List the built image
        list_cmd = [container_tool, 'images', tag]
        run_command(list_cmd, check=False)
        
        return True
    else:
        print(f"[!] Failed to build {tag}")
        return False

def main():
    """Main build task"""
    print("=== PF Task: Build ===")
    
    # Detect container tool
    container_tool = detect_container_tool()
    print(f"[*] Using container tool: {container_tool}")
    
    # Build image
    success = build_image(container_tool)
    
    if success:
        print("[✓] Build task completed successfully")
        sys.exit(0)
    else:
        print("[!] Build task failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
