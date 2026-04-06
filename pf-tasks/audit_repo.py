#!/usr/bin/env python3
"""
PF Task: Audit repository hygiene and layout.

This task detects stale/stray files and structure problems that often appear
after refactors or release-prep iterations.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List


REPO_ROOT = Path(__file__).resolve().parent.parent

IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    ".cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "playwright-report",
    "test-results",
    "htmlcov",
}

SAFE_REMOVE_GLOBS = (
    "*~HEAD",
    "*.orig",
    "*.rej",
)

STALE_VARIANT_SUFFIXES = (
    "_old.html",
    ".deprecated",
)


@dataclass
class Finding:
    kind: str
    severity: str
    path: str
    message: str
    safe_to_fix: bool = False


def _should_skip(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    return any(part in IGNORED_DIR_NAMES for part in rel.parts)


def _iter_paths(repo_root: Path) -> Iterable[Path]:
    for path in repo_root.rglob("*"):
        if _should_skip(path, repo_root):
            continue
        yield path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_stale_backups(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for pattern in SAFE_REMOVE_GLOBS:
        for path in repo_root.rglob(pattern):
            if _should_skip(path, repo_root) or not path.is_file():
                continue
            findings.append(
                Finding(
                    kind="stale-backup-file",
                    severity="medium",
                    path=str(path.relative_to(repo_root)),
                    message=f"Matched stale backup pattern: {pattern}",
                    safe_to_fix=True,
                )
            )
    return findings


def find_broken_symlinks(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in _iter_paths(repo_root):
        if path.is_symlink() and not path.exists():
            findings.append(
                Finding(
                    kind="broken-symlink",
                    severity="high",
                    path=str(path.relative_to(repo_root)),
                    message="Symlink target does not exist",
                    safe_to_fix=False,
                )
            )
    return findings


def find_duplicate_entrypoints(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for right in _iter_paths(repo_root):
        if not right.is_file() or not right.name.endswith("_refactored.py"):
            continue

        left_name = right.name.replace("_refactored.py", ".py")
        left = right.with_name(left_name)
        if not left.exists() or not left.is_file():
            continue

        if _sha256(left) == _sha256(right):
            left_rel = str(left.relative_to(repo_root))
            right_rel = str(right.relative_to(repo_root))
            findings.append(
                Finding(
                    kind="duplicate-file-content",
                    severity="low",
                    path=right_rel,
                    message=f"Duplicate content of {left_rel}; consider consolidating",
                    safe_to_fix=False,
                )
            )
    return findings


def find_stale_variants(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in _iter_paths(repo_root):
        if not path.is_file():
            continue
        rel = str(path.relative_to(repo_root))
        for suffix in STALE_VARIANT_SUFFIXES:
            if path.name.endswith(suffix):
                findings.append(
                    Finding(
                        kind="stale-variant-file",
                        severity="medium",
                        path=rel,
                        message=f"Likely legacy variant file ending in {suffix}",
                        safe_to_fix=False,
                    )
                )
                break
    return findings


def find_nested_duplicate_dirs(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in _iter_paths(repo_root):
        if not path.is_dir():
            continue
        rel = path.relative_to(repo_root)
        parts = rel.parts
        for idx in range(1, len(parts)):
            if parts[idx] == parts[idx - 1]:
                findings.append(
                    Finding(
                        kind="nested-duplicate-dir",
                        severity="medium",
                        path=str(rel),
                        message="Repeated directory name in path",
                        safe_to_fix=False,
                    )
                )
                break
    return findings


def run_audit(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    findings.extend(find_stale_backups(repo_root))
    findings.extend(find_broken_symlinks(repo_root))
    findings.extend(find_duplicate_entrypoints(repo_root))
    findings.extend(find_stale_variants(repo_root))
    findings.extend(find_nested_duplicate_dirs(repo_root))
    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(
        key=lambda item: (
            severity_order.get(item.severity, 99),
            item.kind,
            item.path,
        )
    )
    return findings


def apply_safe_fixes(repo_root: Path, findings: List[Finding]) -> List[str]:
    removed: List[str] = []
    for finding in findings:
        if not finding.safe_to_fix:
            continue
        target = repo_root / finding.path
        if target.exists() and target.is_file():
            target.unlink()
            removed.append(finding.path)
    return sorted(set(removed))


def print_text_report(findings: List[Finding], removed: List[str]) -> None:
    print("=== PF Task: Repo Audit ===")
    if not findings:
        print("[OK] No issues found")
        return

    sev_counts = {"high": 0, "medium": 0, "low": 0}
    for finding in findings:
        sev_counts[finding.severity] = sev_counts.get(finding.severity, 0) + 1
        print(
            f"[{finding.severity.upper()}] {finding.path} :: "
            f"{finding.kind} :: {finding.message}"
        )

    print(
        "\nSummary: "
        f"high={sev_counts['high']}, "
        f"medium={sev_counts['medium']}, "
        f"low={sev_counts['low']}, "
        f"total={len(findings)}"
    )
    if removed:
        print("\nSafe fixes applied:")
        for path in removed:
            print(f"- removed {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit repository hygiene")
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Path to repository root (default: auto-detected)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code when issues are found",
    )
    parser.add_argument(
        "--apply-safe-fixes",
        action="store_true",
        help="Remove only files considered low-risk stale backups",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of text",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    findings = run_audit(repo_root)
    removed: List[str] = []

    if args.apply_safe_fixes and findings:
        removed = apply_safe_fixes(repo_root, findings)
        if removed:
            findings = run_audit(repo_root)

    if args.json:
        payload = {
            "repo_root": str(repo_root),
            "findings": [asdict(item) for item in findings],
            "safe_fixes_removed": removed,
            "total_findings": len(findings),
        }
        print(json.dumps(payload, indent=2))
    else:
        print_text_report(findings, removed)

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
