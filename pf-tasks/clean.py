#!/usr/bin/env python3
"""
PF Task: Clean up opsechat deployment and resources
Compatible with pf-web-poly-compile-helper-runner patterns
"""

import subprocess
import sys
import shutil
import os
import re
from pathlib import Path
import argparse


ARTIFACT_FILENAMES = {".bish-index", ".bish.sqlite"}
REPO_SCAN_SKIP_DIRS = {
    ".git",
    ".venv",
    ".cache",
    "node_modules",
    "playwright-report",
    "test-results",
    "__pycache__",
}
MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|STUB|TBD|WIP|HACK|XXX)\b")
MARKER_FILE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".sh", ".yml", ".yaml", ".json"}
STALE_DUPLICATE_CANDIDATES = {
    "runserver_refactored.py": "runserver.py",
    "tests/mock_server_refactored.py": "tests/mock_server.py",
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


def iter_repo_files(project_root):
    """Yield repo files while pruning noisy or archived directories."""
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in REPO_SCAN_SKIP_DIRS]
        root_path = Path(root)
        for filename in files:
            yield root_path / filename


def find_artifact_files(project_root):
    """Find tracked/generated artifact files that should not live in git."""
    artifact_files = []
    for file_path in iter_repo_files(project_root):
        if file_path.name in ARTIFACT_FILENAMES:
            artifact_files.append(file_path)
    return sorted(artifact_files)


def find_stale_duplicates(project_root):
    """Find stale duplicate files that are byte-identical to canonical files."""
    stale_files = []
    for stale_rel, canonical_rel in STALE_DUPLICATE_CANDIDATES.items():
        stale_path = project_root / stale_rel
        canonical_path = project_root / canonical_rel
        if not stale_path.exists() or not canonical_path.exists():
            continue
        if stale_path.read_bytes() == canonical_path.read_bytes():
            stale_files.append(stale_path)
    return stale_files


def find_unfinished_markers(project_root, include_docs=False):
    """Search for unfinished markers in active code files."""
    marker_hits = []
    for file_path in iter_repo_files(project_root):
        suffix = file_path.suffix.lower()
        if "bak" in file_path.parts:
            continue
        if not include_docs and "docs" in file_path.parts:
            continue
        if suffix == ".md" and include_docs:
            pass
        elif suffix not in MARKER_FILE_SUFFIXES:
            continue
        if file_path.name.endswith(".min.js"):
            continue

        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line_number, line in enumerate(handle, 1):
                    if MARKER_PATTERN.search(line):
                        marker_hits.append((file_path, line_number, line.strip()))
        except OSError:
            continue
    return marker_hits


def remove_files(paths):
    """Remove files and return True when all removals succeed."""
    success = True
    for path in paths:
        try:
            path.unlink()
            print(f"[*] Removed {path}")
        except OSError as exc:
            print(f"[!] Failed to remove {path}: {exc}")
            success = False
    return success


def run_repository_hygiene(project_root, apply=False, include_docs=False):
    """
    Audit and optionally clean repository hygiene issues.

    Returns:
        tuple: (cleanup_ok, marker_hits)
    """
    print("[*] Running repository hygiene audit")
    artifact_files = find_artifact_files(project_root)
    stale_duplicates = find_stale_duplicates(project_root)
    marker_hits = find_unfinished_markers(project_root, include_docs=include_docs)

    print(f"[*] Artifact files detected: {len(artifact_files)}")
    for path in artifact_files:
        print(f"    - {path.relative_to(project_root)}")

    print(f"[*] Stale duplicate files detected: {len(stale_duplicates)}")
    for path in stale_duplicates:
        print(f"    - {path.relative_to(project_root)}")

    if marker_hits:
        print(f"[*] Unfinished markers detected: {len(marker_hits)}")
        for file_path, line_number, line in marker_hits[:30]:
            relative = file_path.relative_to(project_root)
            print(f"    - {relative}:{line_number} {line}")
        if len(marker_hits) > 30:
            print(f"    ... {len(marker_hits) - 30} additional markers omitted")
    else:
        print("[*] No unfinished markers detected in scanned files")

    cleanup_ok = True
    if apply:
        removable_files = artifact_files + stale_duplicates
        if removable_files:
            print("[*] Applying repository cleanup")
            cleanup_ok = remove_files(removable_files)
        else:
            print("[*] No removable repository artifacts found")

    return cleanup_ok, marker_hits

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
        if args.artifacts and not args.images:
            # Only clean artifacts when --artifacts is specified alone
            return None
        if (args.repo_hygiene or args.apply_repo_cleanup) and not args.images and not args.artifacts:
            # Repository cleanup mode should not implicitly stop deployments.
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
                       help='Audit repository for artifact files and unfinished markers')
    parser.add_argument('--apply-repo-cleanup', action='store_true',
                       help='Remove detected artifact files and stale duplicate files')
    parser.add_argument('--include-doc-markers', action='store_true',
                       help='Include docs/*.md files in unfinished marker scan')
    parser.add_argument('--fail-on-markers', action='store_true',
                       help='Exit non-zero if unfinished markers are found during repo hygiene scan')
    
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

    run_repo_hygiene = args.repo_hygiene or args.apply_repo_cleanup
    marker_hits = []
    if run_repo_hygiene:
        repo_ok, marker_hits = run_repository_hygiene(
            Path(__file__).parent.parent,
            apply=args.apply_repo_cleanup,
            include_docs=args.include_doc_markers,
        )
        success &= repo_ok

    if args.fail_on_markers and marker_hits:
        print("[!] Failing due to unfinished markers found during repo hygiene scan")
        success = False
    
    if success:
        print("[✓] Cleanup completed successfully")
        sys.exit(0)
    else:
        print("[!] Some cleanup operations failed")
        sys.exit(1)

if __name__ == "__main__":
    main()