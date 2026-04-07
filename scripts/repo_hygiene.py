#!/usr/bin/env python3
"""
Repository hygiene checker.

Detects common stale artifacts and optional cleanup candidates:
- merge/editor backups (e.g., *~HEAD, *.orig, *.rej)
- Python cache artifacts (__pycache__, *.pyc)
- tracked build/index artifacts (.bish-index/.bish.sqlite)
- nested placeholder workflow files under .github/.github/workflows
- ad-hoc debug scripts at repository root
"""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


BACKUP_PATTERNS = ("*~HEAD", "*.orig", "*.rej")
PY_CACHE_FILE_PATTERNS = ("*.pyc",)
INDEX_ARTIFACT_NAMES = {".bish-index", ".bish.sqlite"}
ROOT_DEBUG_FILES = {"test-ci-fix.js", "test-server.js"}

# Conservative safe cleanup set used by --fix-safe
SAFE_FIXABLE_CATEGORIES = {
    "backup-artifact",
    "python-cache-dir",
    "python-cache-file",
}


@dataclass
class Finding:
    category: str
    path: Path
    detail: str
    fixable: bool = True


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _is_ignored_path(path: Path) -> bool:
    parts = set(path.parts)
    return ".git" in parts or "node_modules" in parts or ".venv" in parts


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_ignored_path(path):
            continue
        yield path


def find_backup_artifacts(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in iter_files(root):
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in BACKUP_PATTERNS):
            findings.append(
                Finding(
                    category="backup-artifact",
                    path=path,
                    detail="Editor/merge backup file",
                    fixable=True,
                )
            )
    return findings


def find_python_cache_artifacts(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in root.rglob("__pycache__"):
        if path.is_dir() and not _is_ignored_path(path):
            findings.append(
                Finding(
                    category="python-cache-dir",
                    path=path,
                    detail="Python bytecode cache directory",
                    fixable=True,
                )
            )

    for path in iter_files(root):
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in PY_CACHE_FILE_PATTERNS):
            findings.append(
                Finding(
                    category="python-cache-file",
                    path=path,
                    detail="Python bytecode cache file",
                    fixable=True,
                )
            )
    return findings


def find_tracked_index_artifacts(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    tracked = run_git(root, "ls-files").splitlines()
    for rel in tracked:
        rel_path = Path(rel)
        if rel_path.name in INDEX_ARTIFACT_NAMES:
            findings.append(
                Finding(
                    category="tracked-build-artifact",
                    path=root / rel_path,
                    detail="Tracked index artifact should normally be ignored",
                    fixable=False,
                )
            )
    return findings


def find_nested_placeholder_workflows(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    nested_workflow_dir = root / ".github" / ".github" / "workflows"
    if not nested_workflow_dir.exists():
        return findings

    for workflow in nested_workflow_dir.glob("*.yml"):
        content = workflow.read_text(encoding="utf-8", errors="ignore").strip()
        if content.startswith("# Placeholder workflow for"):
            findings.append(
                Finding(
                    category="placeholder-workflow",
                    path=workflow,
                    detail="Nested placeholder workflow file",
                    fixable=True,
                )
            )
    return findings


def find_debug_files(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for name in ROOT_DEBUG_FILES:
        path = root / name
        if path.exists():
            findings.append(
                Finding(
                    category="root-debug-file",
                    path=path,
                    detail="Ad-hoc debug script in repository root",
                    fixable=False,
                )
            )
    return findings


def collect_findings(root: Path) -> List[Finding]:
    checks = (
        find_backup_artifacts(root),
        find_python_cache_artifacts(root),
        find_tracked_index_artifacts(root),
        find_nested_placeholder_workflows(root),
        find_debug_files(root),
    )
    findings: List[Finding] = []
    for group in checks:
        findings.extend(group)
    findings.sort(key=lambda f: (f.category, str(f.path)))
    return findings


def remove_path(path: Path) -> bool:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def apply_fixes(root: Path, findings: List[Finding], safe_only: bool) -> List[str]:
    actions: List[str] = []
    for finding in findings:
        rel = finding.path.relative_to(root)
        allowed = finding.fixable and (
            not safe_only or finding.category in SAFE_FIXABLE_CATEGORIES
        )
        if not allowed:
            actions.append(f"skipped {rel}")
            continue
        if remove_path(finding.path):
            actions.append(f"removed {rel}")
        else:
            actions.append(f"failed {rel}")

    # Remove empty nested placeholder directory if cleanup removed all files.
    for maybe_empty in (
        root / ".github" / ".github" / "workflows",
        root / ".github" / ".github",
    ):
        try:
            maybe_empty.rmdir()
        except OSError:
            pass

    return actions


def build_summary(
    root: Path, findings: List[Finding], actions: List[str], max_stale_days: int
) -> str:
    lines = ["## Repository Hygiene Report", ""]
    lines.append(f"- Root: `{root}`")
    lines.append(f"- Findings: **{len(findings)}**")
    lines.append(f"- Stale threshold hint: `{max_stale_days}` days")
    lines.append("")

    if findings:
        lines.append("### Findings")
        for item in findings:
            rel = item.path.relative_to(root)
            lines.append(f"- `{item.category}`: `{rel}` - {item.detail}")
        lines.append("")
    else:
        lines.append("No hygiene issues detected.")
        lines.append("")

    if actions:
        lines.append("### Applied Fixes")
        for action in actions:
            lines.append(f"- {action}")
        lines.append("")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check repository hygiene.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Repository root path (defaults to project root).",
    )
    parser.add_argument(
        "--fix-safe",
        action="store_true",
        help="Apply conservative cleanup for known-safe stale artifacts.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply broader cleanup for all fixable findings.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when findings exist.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Alias for --check (kept for workflow compatibility).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print markdown report to stdout.",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=30,
        help="Staleness threshold hint for report context.",
    )
    parser.add_argument(
        "--write-summary",
        default="",
        help="Optional markdown output path for findings summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    findings = collect_findings(root)
    actions: List[str] = []

    if args.fix_safe and findings:
        actions = apply_fixes(root, findings, safe_only=True)
        findings = collect_findings(root)
    elif args.fix and findings:
        actions = apply_fixes(root, findings, safe_only=False)
        findings = collect_findings(root)

    summary = build_summary(root, findings, actions, args.max_stale_days)

    if args.write_summary:
        Path(args.write_summary).write_text(summary, encoding="utf-8")
    if args.report or not args.write_summary:
        sys.stdout.write(summary)

    if (args.check or args.strict) and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
