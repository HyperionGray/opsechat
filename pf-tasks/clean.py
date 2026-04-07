#!/usr/bin/env python3
"""
PF Task: Clean up opsechat deployment and resources
Compatible with pf-web-poly-compile-helper-runner patterns
"""

import subprocess
import sys
import shutil
import os
from fnmatch import fnmatch
from pathlib import Path
import argparse

REPO_HYGIENE_RULES = [
    {
        "pattern": "*~HEAD",
        "reason": "git merge backup artifact",
        "auto_remove": True,
    },
    {
        "pattern": "*.orig",
        "reason": "patch/merge backup artifact",
        "auto_remove": True,
    },
    {
        "pattern": "*.rej",
        "reason": "failed patch artifact",
        "auto_remove": True,
    },
]

REPO_HYGIENE_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
}

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
        'opsechat.network',
        'opsechat-network.service',  # legacy name cleanup
        'opsechat-tor.service',
        'opsechat-app.service'
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
        'opsechat.network',
        'opsechat-cleanup.timer',
        'opsechat-cleanup.service',
        'tor-data.volume'
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
    compose_down_script = project_root / "scripts" / "compose-down.sh"
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

def is_tracked_by_git(project_root, relative_path):
    """Check whether a path is tracked by git."""
    result = subprocess.run(
        ['git', '-C', str(project_root), 'ls-files', '--error-unmatch', relative_path],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def find_repo_hygiene_candidates(project_root):
    """Find stale/backup files that should not stay in the repository."""
    candidates = []

    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in REPO_HYGIENE_SKIP_DIRS]
        root_path = Path(root)

        for file_name in files:
            matched_rule = None
            for rule in REPO_HYGIENE_RULES:
                if fnmatch(file_name, rule["pattern"]):
                    matched_rule = rule
                    break

            if not matched_rule:
                continue

            abs_path = root_path / file_name
            rel_path = str(abs_path.relative_to(project_root))
            tracked = is_tracked_by_git(project_root, rel_path)

            candidates.append({
                "path": abs_path,
                "relative_path": rel_path,
                "reason": matched_rule["reason"],
                "auto_remove": matched_rule["auto_remove"],
                "tracked": tracked,
            })

    candidates.sort(key=lambda item: item["relative_path"])
    return candidates

def clean_repository_hygiene(apply=False):
    """Report or remove stale repository files."""
    print("[*] Scanning repository for stale/backup files")
    project_root = Path(__file__).parent.parent
    candidates = find_repo_hygiene_candidates(project_root)

    if not candidates:
        print("[✓] No repository hygiene issues found")
        return True

    print(f"[!] Found {len(candidates)} repository hygiene candidate(s):")
    for item in candidates:
        tracked_state = "tracked" if item["tracked"] else "untracked"
        print(f"    - {item['relative_path']} [{tracked_state}] ({item['reason']})")

    if not apply:
        print("[*] Report only. Re-run with --repo-apply to remove auto-removable files.")
        return True

    removed = 0
    failed = 0
    for item in candidates:
        if not item["auto_remove"]:
            continue

        try:
            item["path"].unlink(missing_ok=True)
            print(f"[*] Removed {item['relative_path']}")
            removed += 1
        except OSError as exc:
            print(f"[!] Failed to remove {item['relative_path']}: {exc}")
            failed += 1

    print(f"[*] Repository cleanup removed {removed} file(s)")
    if failed:
        print(f"[!] Failed to remove {failed} file(s)")
        return False

    return True

def determine_cleanup_method(args):
    """
    Determine which cleanup method to use based on arguments.
    
    Returns:
        str or None: The effective cleanup method:
            - None: Skip deployment cleanup and only run selective cleanup flags
              (--artifacts and/or --repo without --method or --images)
            - 'all': Clean all deployment artifacts - systemd, compose, and containers (default behavior)
            - 'systemd', 'compose', 'containers': Clean only specific deployment type
            
    Note: Images, build artifacts, and repository hygiene checks are only cleaned when
    their respective flags (--images, --artifacts, --repo/--repo-apply) are set.
    """
    if args.method is None:
        if (args.artifacts or args.repo or args.repo_apply) and not args.images:
            # Selective cleanup mode when only non-deployment flags are requested
            return None
        else:
            # Default to 'all' for other cases (no args, --images alone, etc.)
            return 'all'
    else:
        # Explicit method specified
        return args.method

def main():
    """Main cleanup task"""
    parser = argparse.ArgumentParser(description='Clean up opsechat deployment')
    parser.add_argument('--method', choices=['systemd', 'compose', 'containers', 'all'], 
                       default=None, help='Cleanup method')
    parser.add_argument('--images', action='store_true', help='Also remove container images')
    parser.add_argument('--force', action='store_true', help='Force removal of images')
    parser.add_argument('--artifacts', action='store_true', help='Clean build artifacts')
    parser.add_argument('--repo', action='store_true',
                       help='Scan repository for stale backup files')
    parser.add_argument('--repo-apply', action='store_true',
                       help='Remove stale repository files detected by --repo scan')
    
    args = parser.parse_args()
    
    # Determine effective cleanup method
    effective_method = determine_cleanup_method(args)
    
    print("=== PF Task: Clean ===")
    
    success = True
    
    if effective_method in ['systemd', 'all']:
        success &= clean_systemd_services()
    
    if effective_method in ['compose', 'all']:
        success &= clean_compose()
    
    if effective_method in ['containers', 'all']:
        success &= clean_containers()
    
    # Only clean images if explicitly requested via --images flag
    if args.images:
        success &= clean_images(force=args.force)
    
    # Only clean artifacts if explicitly requested via --artifacts flag
    if args.artifacts:
        success &= clean_build_artifacts()

    # Repository hygiene pass (scan/report by default, remove with --repo-apply)
    if args.repo or args.repo_apply:
        success &= clean_repository_hygiene(apply=args.repo_apply)
    
    if success:
        print("[✓] Cleanup completed successfully")
        sys.exit(0)
    else:
        print("[!] Some cleanup operations failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
