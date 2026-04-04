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
from typing import Dict, List

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


def _list_tracked_files(project_root: Path) -> List[str]:
    """Return tracked files from git index."""
    try:
        result = subprocess.run(
            ['git', 'ls-files'],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def scan_repo_hygiene(project_root: Path) -> Dict[str, List[str]]:
    """
    Scan repository for stale tracked artifacts and broken symlinks.

    Returns:
        dict with keys:
          - tracked_backups: tracked *~HEAD files
          - tracked_bish_artifacts: tracked .bish-index/.bish.sqlite files
          - broken_symlinks: broken symlinks anywhere in repo (excluding .git)
    """
    tracked_files = _list_tracked_files(project_root)
    tracked_set = set(tracked_files)

    tracked_backups = sorted([
        path for path in tracked_files if path.endswith('~HEAD')
    ])
    tracked_bish_artifacts = sorted([
        path for path in tracked_files if Path(path).name in {'.bish-index', '.bish.sqlite'}
    ])

    broken_symlinks: List[str] = []
    for path in project_root.rglob('*'):
        if '.git' in path.parts:
            continue
        if path.is_symlink() and not path.exists():
            broken_symlinks.append(str(path.relative_to(project_root)))

    return {
        'tracked_backups': tracked_backups,
        'tracked_bish_artifacts': tracked_bish_artifacts,
        'broken_symlinks': sorted(broken_symlinks),
        'tracked_set': sorted(tracked_set),
    }


def _print_repo_hygiene_report(findings: Dict[str, List[str]]) -> None:
    """Print repo hygiene findings in a readable summary."""
    tracked_backups = findings.get('tracked_backups', [])
    tracked_bish = findings.get('tracked_bish_artifacts', [])
    broken_symlinks = findings.get('broken_symlinks', [])

    print("[*] Repository hygiene report")
    print(f"    - tracked backup files (~HEAD): {len(tracked_backups)}")
    print(f"    - tracked .bish artifacts: {len(tracked_bish)}")
    print(f"    - broken symlinks: {len(broken_symlinks)}")

    for label, items in [
        ("tracked backup", tracked_backups),
        ("tracked .bish artifact", tracked_bish),
        ("broken symlink", broken_symlinks),
    ]:
        if items:
            print(f"[*] {label} entries:")
            for item in items:
                print(f"    - {item}")


def apply_repo_hygiene_fixes(project_root: Path, findings: Dict[str, List[str]]) -> bool:
    """Remove detected stale files and broken symlinks."""
    tracked_set = set(findings.get('tracked_set', []))
    removal_candidates = sorted(set(
        findings.get('tracked_backups', [])
        + findings.get('tracked_bish_artifacts', [])
        + findings.get('broken_symlinks', [])
    ))

    if not removal_candidates:
        print("[*] No repo hygiene fixes needed")
        return True

    print("[*] Applying repository hygiene fixes")
    success = True

    for rel_path in removal_candidates:
        abs_path = project_root / rel_path
        if rel_path in tracked_set:
            print(f"[*] Removing tracked file: {rel_path}")
            result = run_command(
                ['git', 'rm', '-f', '--', rel_path],
                cwd=project_root,
                check=False
            )
            if result.returncode != 0:
                success = False
            continue

        if abs_path.is_symlink() or abs_path.exists():
            print(f"[*] Removing file/symlink: {rel_path}")
            try:
                abs_path.unlink(missing_ok=True)
            except OSError as exc:
                print(f"[!] Failed to remove {rel_path}: {exc}")
                success = False

    return success

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
        if (args.repo_hygiene or args.repo_hygiene_fix) and not args.images and not args.artifacts:
            # Repo hygiene-only mode should not touch deployment resources by default
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
    parser.add_argument(
        '--repo-hygiene',
        action='store_true',
        help='Audit repository for stale tracked backups/artifacts and broken symlinks'
    )
    parser.add_argument(
        '--repo-hygiene-fix',
        action='store_true',
        help='Apply repo hygiene fixes (removes findings from --repo-hygiene audit)'
    )
    
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

    if args.repo_hygiene or args.repo_hygiene_fix:
        project_root = Path(__file__).parent.parent
        findings = scan_repo_hygiene(project_root)
        _print_repo_hygiene_report(findings)
        if args.repo_hygiene_fix:
            success &= apply_repo_hygiene_fixes(project_root, findings)
    
    if success:
        print("[✓] Cleanup completed successfully")
        sys.exit(0)
    else:
        print("[!] Some cleanup operations failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
