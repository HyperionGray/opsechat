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
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

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
        else:
            # Default to 'all' for other cases (no args, --images alone, etc.)
            return 'all'
    else:
        # Explicit method specified
        return args.method

def build_cleanup_plan(effective_method: str, include_images: bool, include_artifacts: bool, force_images: bool = False) -> List[Dict[str, Any]]:
    """Build an ordered cleanup plan from CLI options."""
    plan: List[Dict[str, Any]] = []

    if effective_method in ['systemd', 'all']:
        plan.append({
            'name': 'systemd_services',
            'description': 'stop/disable user services and remove quadlet files',
            'callable': clean_systemd_services
        })

    if effective_method in ['compose', 'all']:
        plan.append({
            'name': 'compose',
            'description': 'run compose teardown with local scripts/tools',
            'callable': clean_compose
        })

    if effective_method in ['containers', 'all']:
        plan.append({
            'name': 'containers',
            'description': 'stop/remove containers, network, and volumes',
            'callable': clean_containers
        })

    if include_images:
        image_description = 'remove container images'
        if force_images:
            image_description += ' (forced)'
        plan.append({
            'name': 'images',
            'description': image_description,
            'callable': lambda: clean_images(force=force_images)
        })

    if include_artifacts:
        plan.append({
            'name': 'build_artifacts',
            'description': 'remove Python caches and local test artifacts',
            'callable': clean_build_artifacts
        })

    return plan

def execute_cleanup_plan(plan: List[Dict[str, Any]], dry_run: bool = False) -> Tuple[bool, List[Dict[str, Any]]]:
    """Execute or preview plan and return overall success + per-step results."""
    overall_success = True
    step_results: List[Dict[str, Any]] = []

    for step in plan:
        name = step['name']
        description = step['description']
        print(f"[*] Step {name}: {description}")

        if dry_run:
            step_results.append({
                'name': name,
                'description': description,
                'status': 'planned',
                'success': None
            })
            continue

        try:
            step_success = bool(step['callable']())
        except Exception as exc:
            step_success = False
            print(f"[!] Step {name} raised an exception: {exc}")

        overall_success &= step_success
        step_results.append({
            'name': name,
            'description': description,
            'status': 'completed' if step_success else 'failed',
            'success': step_success
        })

    return overall_success, step_results

def write_cleanup_report(report_file: str, report_data: Dict[str, Any]) -> None:
    """Write cleanup report as JSON for automation and auditing."""
    report_path = Path(report_file)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_data, indent=2) + "\n", encoding='utf-8')
    print(f"[*] Wrote cleanup report: {report_path}")

def main():
    """Main cleanup task"""
    parser = argparse.ArgumentParser(description='Clean up opsechat deployment')
    parser.add_argument('--method', choices=['systemd', 'compose', 'containers', 'all'], 
                       default=None, help='Cleanup method')
    parser.add_argument('--images', action='store_true', help='Also remove container images')
    parser.add_argument('--force', action='store_true', help='Force removal of images')
    parser.add_argument('--artifacts', action='store_true', help='Clean build artifacts')
    parser.add_argument('--dry-run', action='store_true', help='Preview cleanup actions without executing')
    parser.add_argument('--report-file', help='Write JSON cleanup report to this path')
    
    args = parser.parse_args()
    
    # Determine effective cleanup method
    effective_method = determine_cleanup_method(args)
    
    print("=== PF Task: Clean ===")
    
    cleanup_plan = build_cleanup_plan(
        effective_method=effective_method,
        include_images=args.images,
        include_artifacts=args.artifacts,
        force_images=args.force
    )

    if not cleanup_plan:
        print("[*] No cleanup actions requested")

    if args.dry_run:
        print("[*] Dry-run mode enabled. No changes will be made.")

    success, step_results = execute_cleanup_plan(cleanup_plan, dry_run=args.dry_run)

    report_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'mode': 'dry-run' if args.dry_run else 'execute',
        'effective_method': effective_method,
        'options': {
            'method': args.method,
            'images': args.images,
            'force': args.force,
            'artifacts': args.artifacts,
            'dry_run': args.dry_run
        },
        'steps': step_results,
        'success': success
    }

    if args.report_file:
        write_cleanup_report(args.report_file, report_data)

    if args.dry_run:
        print("[✓] Dry-run completed successfully")
        sys.exit(0)

    if success:
        print("[✓] Cleanup completed successfully")
        sys.exit(0)

    print("[!] Some cleanup operations failed")
    sys.exit(1)

if __name__ == "__main__":
    main()
