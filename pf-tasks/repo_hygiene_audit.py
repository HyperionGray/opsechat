#!/usr/bin/env python3
"""
PF Task: repository hygiene audit and cleanup.

This task is intentionally conservative: it only reports (or fixes) a narrow
set of well-known stale artifacts that have repeatedly shown up in this repo.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


NESTED_GITHUB_PREFIX = ".github/.github/"
KNOWN_EMPTY_FILE_PATHS = {".github/d"}


@dataclass(frozen=True)
class Issue:
    kind: str
    path: str
    message: str
    fixable: bool = True


def run_command(cmd: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def tracked_files(repo_root: Path) -> List[str]:
    result = run_command(["git", "ls-files"], cwd=repo_root)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_placeholder_workflow(file_path: Path) -> bool:
    if not file_path.exists() or file_path.suffix not in {".yml", ".yaml"}:
        return False
    try:
        content = file_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return content.startswith("# Placeholder workflow for ")


def _path_issue_for_file(repo_root: Path, relative_path: str) -> Iterable[Issue]:
    file_path = repo_root / relative_path
    name = file_path.name

    if name.endswith("~HEAD"):
        yield Issue(
            kind="backup-file",
            path=relative_path,
            message="Backup artifact tracked in git",
            fixable=True,
        )

    if name == ".bish-index":
        yield Issue(
            kind="build-artifact",
            path=relative_path,
            message="BISH build index should not be tracked",
            fixable=True,
        )

    if relative_path.startswith(NESTED_GITHUB_PREFIX):
        yield Issue(
            kind="nested-github-workflow",
            path=relative_path,
            message="Workflow file under nested .github/.github path",
            fixable=True,
        )

    if relative_path in KNOWN_EMPTY_FILE_PATHS and file_path.exists() and file_path.stat().st_size == 0:
        yield Issue(
            kind="empty-stray-file",
            path=relative_path,
            message="Known stray empty file",
            fixable=True,
        )

    if is_placeholder_workflow(file_path):
        yield Issue(
            kind="placeholder-workflow",
            path=relative_path,
            message="Placeholder workflow should be replaced or removed",
            fixable=True,
        )


def scan_repository(repo_root: Path, files: Sequence[str]) -> List[Issue]:
    issues: List[Issue] = []
    for rel_path in files:
        issues.extend(_path_issue_for_file(repo_root, rel_path))

    # Deduplicate by (kind, path) in case multiple checks overlap.
    deduped: List[Issue] = []
    seen = set()
    for issue in issues:
        key = (issue.kind, issue.path)
        if key not in seen:
            seen.add(key)
            deduped.append(issue)
    return deduped


def _remove_empty_parent_dirs(repo_root: Path, removed_file: Path) -> None:
    current = removed_file.parent
    stop = repo_root
    while current != stop:
        if any(current.iterdir()):
            break
        current.rmdir()
        current = current.parent


def apply_fixes(repo_root: Path, issues: Sequence[Issue]) -> int:
    removed = 0
    removed_paths = set()
    for issue in issues:
        if not issue.fixable or issue.path in removed_paths:
            continue
        target = repo_root / issue.path
        if target.exists() and target.is_file():
            target.unlink()
            _remove_empty_parent_dirs(repo_root, target)
            removed_paths.add(issue.path)
            removed += 1
    return removed


def print_report(issues: Sequence[Issue]) -> None:
    if not issues:
        print("[✓] Repo hygiene check passed: no stale artifacts found.")
        return

    print(f"[!] Repo hygiene check found {len(issues)} issue(s):")
    for issue in issues:
        print(f"  - [{issue.kind}] {issue.path}: {issue.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit repository hygiene and optionally fix stale artifacts.")
    parser.add_argument(
        "--mode",
        choices=["check", "fix"],
        default="check",
        help="check = report only; fix = remove known stale files",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Alias for --mode check",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Alias for --mode fix",
    )
    args = parser.parse_args()

    mode = args.mode
    if args.check and args.fix:
        print("[!] Use only one of --check or --fix.")
        sys.exit(2)
    if args.check:
        mode = "check"
    if args.fix:
        mode = "fix"

    repo_root = Path(__file__).resolve().parent.parent
    files = tracked_files(repo_root)
    issues = scan_repository(repo_root, files)
    print_report(issues)

    if mode == "fix":
        removed = apply_fixes(repo_root, issues)
        print(f"[*] Removed {removed} file(s).")

        # Re-run report after fixing.
        remaining = scan_repository(repo_root, tracked_files(repo_root))
        if remaining:
            print("[!] Some issues remain after auto-fix:")
            print_report(remaining)
            sys.exit(1)

        print("[✓] Repo hygiene auto-fix complete.")
        sys.exit(0)

    # check mode
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
