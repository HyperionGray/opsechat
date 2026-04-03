#!/usr/bin/env python3
"""
PF Task: Clean up opsechat deployment and resources
Compatible with pf-web-poly-compile-helper-runner patterns
"""

import subprocess
import sys
import shutil
from pathlib import Path
import argparse


STALE_FILE_PATTERNS = (
    "*~HEAD",
    "*.orig",
    "*.rej",
    "*.bak",
    "*.tmp",
    "*.temp",
    ".DS_Store",
)

SKIP_SCAN_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "bak",
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
    test_dirs = ['test-results', 'playwright-report', '.pytest_cache', '.cache']
    for test_dir in test_dirs:
        test_path = project_root / test_dir
        if test_path.exists():
            print(f"[*] Removing {test_path}")
            shutil.rmtree(test_path, ignore_errors=True)
    
    return True


def _iter_repo_paths(project_root):
    """
    Yield files and directories while skipping noisy dependency/build trees.
    """
    for path in project_root.rglob("*"):
        rel_parts = path.relative_to(project_root).parts
        if any(part in SKIP_SCAN_DIRS for part in rel_parts):
            continue
        yield path


def find_stale_files(project_root):
    """Find stale/merge artifact files that should not stay in the repo."""
    stale_files = set()
    for pattern in STALE_FILE_PATTERNS:
        for path in project_root.rglob(pattern):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(project_root).parts
            if any(part in SKIP_SCAN_DIRS for part in rel_parts):
                continue
            stale_files.add(path)

    return sorted(stale_files, key=lambda p: str(p.relative_to(project_root)))


def find_redundant_directory_paths(project_root):
    """
    Find directories with repeated adjacent names (e.g. src/src or build/build).
    """
    redundant = []
    for path in _iter_repo_paths(project_root):
        if not path.is_dir():
            continue
        parts = path.relative_to(project_root).parts
        for idx in range(len(parts) - 1):
            if parts[idx] == parts[idx + 1]:
                redundant.append(path)
                break

    return sorted(set(redundant), key=lambda p: str(p.relative_to(project_root)))


def find_deep_directories(project_root, max_depth_warning):
    """Find directories deeper than max_depth_warning for organization review."""
    deep_dirs = []
    for path in _iter_repo_paths(project_root):
        if not path.is_dir():
            continue
        depth = len(path.relative_to(project_root).parts)
        if depth > max_depth_warning:
            deep_dirs.append(path)

    return sorted(deep_dirs, key=lambda p: str(p.relative_to(project_root)))


def collect_repo_hygiene_issues(project_root, max_depth_warning=6):
    """Collect repository hygiene issues for reporting/fixing."""
    return {
        "stale_files": find_stale_files(project_root),
        "redundant_dirs": find_redundant_directory_paths(project_root),
        "deep_dirs": find_deep_directories(project_root, max_depth_warning=max_depth_warning),
    }


def print_repo_hygiene_report(project_root, issues, max_depth_warning):
    """Print a human-readable hygiene report."""
    stale_files = issues["stale_files"]
    redundant_dirs = issues["redundant_dirs"]
    deep_dirs = issues["deep_dirs"]

    print("[*] Repository hygiene report")

    if stale_files:
        print(f"[!] Stale files found ({len(stale_files)}):")
        for path in stale_files:
            print(f"    - {path.relative_to(project_root)}")
    else:
        print("[✓] No stale files found")

    if redundant_dirs:
        print(f"[!] Redundant directory nesting found ({len(redundant_dirs)}):")
        for path in redundant_dirs:
            print(f"    - {path.relative_to(project_root)}")
    else:
        print("[✓] No redundant adjacent directory names found")

    if deep_dirs:
        print(
            f"[!] Deep directory paths found ({len(deep_dirs)}) "
            f"deeper than {max_depth_warning} levels:"
        )
        for path in deep_dirs:
            print(f"    - {path.relative_to(project_root)}")
    else:
        print(f"[✓] No directories deeper than {max_depth_warning} levels")


def remove_stale_files(stale_files):
    """Remove stale files and return how many were deleted."""
    removed = 0
    for path in stale_files:
        try:
            path.unlink()
            print(f"[*] Removed stale file: {path}")
            removed += 1
        except FileNotFoundError:
            continue
        except PermissionError:
            print(f"[!] Permission denied removing stale file: {path}")
    return removed


def clean_repo_hygiene(fix=False, max_depth_warning=6):
    """
    Scan repository for hygiene issues.
    If fix=True, stale files are removed automatically.
    """
    print("[*] Running repository hygiene scan")
    project_root = Path(__file__).parent.parent
    issues = collect_repo_hygiene_issues(
        project_root,
        max_depth_warning=max_depth_warning,
    )
    print_repo_hygiene_report(project_root, issues, max_depth_warning=max_depth_warning)

    if fix and issues["stale_files"]:
        removed = remove_stale_files(issues["stale_files"])
        print(f"[✓] Removed {removed} stale file(s)")

    return True

def determine_cleanup_method(args):
    """
    Determine which cleanup method to use based on arguments.
    
    Returns:
        str or None: The effective cleanup method:
            - None: Skip deployment cleanup, only clean artifacts (--artifacts without --method or --images)
            - 'all': Clean all deployment artifacts - systemd, compose, and containers (default behavior)
            - 'systemd', 'compose', 'containers': Clean only specific deployment type
            
    Note: Images and build artifacts are only cleaned when their respective flags (--images, --artifacts) are set.
    """
    if args.method is None:
        if (args.repo_hygiene or args.fix_repo_hygiene) and not args.images and not args.artifacts:
            # Safety: repository hygiene scans should not implicitly stop/remove deployments.
            return None
        if args.artifacts and not args.images:
            # Only clean artifacts when --artifacts is specified alone
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
    parser.add_argument('--repo-hygiene', action='store_true',
                        help='Scan repository for stale files and structure issues')
    parser.add_argument('--fix-repo-hygiene', action='store_true',
                        help='Remove stale files discovered by --repo-hygiene scan')
    parser.add_argument('--max-depth-warning', type=int, default=6,
                        help='Directory depth threshold for hygiene warnings')
    
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

    if args.repo_hygiene or args.fix_repo_hygiene:
        success &= clean_repo_hygiene(
            fix=args.fix_repo_hygiene,
            max_depth_warning=args.max_depth_warning,
        )
    
    if success:
        print("[✓] Cleanup completed successfully")
        sys.exit(0)
    else:
        print("[!] Some cleanup operations failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
