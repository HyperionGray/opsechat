#!/usr/bin/env python3
"""
PF Task: Audit repository hygiene and unfinished work
Compatible with pf-web-poly-compile-helper-runner patterns
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

DEFAULT_MARKERS: Tuple[str, ...] = (
    "TODO",
    "FIXME",
    "STUB",
    "TBD",
    "UNFINISHED",
    "WIP",
    "XXX",
    "HACK",
)

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".cache",
    ".venv",
    "venv",
    "deadenv",
    "node_modules",
    "dist",
    "build",
    "playwright-report",
    "test-results",
    ".pytest_cache",
}

TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".cfg",
    ".container",
    ".cpp",
    ".css",
    ".env",
    ".go",
    ".h",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".network",
    ".py",
    ".rb",
    ".rs",
    ".service",
    ".sh",
    ".sql",
    ".tf",
    ".timer",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".volume",
    ".xml",
    ".yaml",
    ".yml",
}

SPECIAL_TEXT_FILENAMES = {"Dockerfile", "Makefile", "Jenkinsfile", "Procfile"}

STALE_SUFFIXES = (".bak", ".old", ".orig", ".tmp")
STALE_SUBSTRINGS = (".deprecated", "_deprecated", "-deprecated")


def run_command(cmd: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a command and return the completed process."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def list_tracked_files(repo_root: Path) -> List[Path]:
    """Return tracked files from git."""
    result = run_command(["git", "ls-files"], cwd=repo_root)
    if result.returncode != 0:
        print(f"[!] git ls-files failed: {result.stderr.strip()}", file=sys.stderr)
        return []
    files: List[Path] = []
    for line in result.stdout.splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue
        files.append(repo_root / clean_line)
    return files


def is_text_file(path: Path) -> bool:
    """Heuristic text-file check by extension and common filenames."""
    if path.name in SPECIAL_TEXT_FILENAMES:
        return True
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return False


def should_exclude(path: Path, repo_root: Path, excluded_dirs: Iterable[str]) -> bool:
    """Return True if path is under an excluded directory."""
    try:
        rel_parts = path.relative_to(repo_root).parts
    except ValueError:
        return True
    return any(part in excluded_dirs for part in rel_parts)


def marker_pattern(markers: Sequence[str]) -> re.Pattern[str]:
    escaped = [re.escape(marker) for marker in markers]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b")


def scan_unfinished_markers(
    repo_root: Path,
    files: Sequence[Path],
    markers: Sequence[str],
    excluded_dirs: Iterable[str],
) -> List[Dict[str, object]]:
    """Find unfinished markers in tracked text files."""
    pattern = marker_pattern(markers)
    findings: List[Dict[str, object]] = []

    for file_path in files:
        if not file_path.exists():
            continue
        if should_exclude(file_path, repo_root, excluded_dirs):
            continue
        if not is_text_file(file_path):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel_path = str(file_path.relative_to(repo_root))
        for line_no, line in enumerate(content.splitlines(), start=1):
            match = pattern.search(line)
            if not match:
                continue
            findings.append(
                {
                    "path": rel_path,
                    "line": line_no,
                    "marker": match.group(1),
                    "snippet": line.strip(),
                }
            )
    return findings


def classify_stale_candidate(rel_path: str, abs_path: Path) -> str:
    """Return stale reason string if path looks stale, otherwise empty string."""
    lower = rel_path.lower()
    for suffix in STALE_SUFFIXES:
        if lower.endswith(suffix):
            return f"stale suffix {suffix}"
    for chunk in STALE_SUBSTRINGS:
        if chunk in lower:
            return f"deprecated naming pattern {chunk}"
    if abs_path.name == "d":
        return "single-letter ambiguous filename"
    try:
        # Empty package marker modules are intentional in many Python layouts.
        if abs_path.name == "__init__.py" and abs_path.is_file() and abs_path.stat().st_size == 0:
            return ""
        if abs_path.is_file() and abs_path.stat().st_size == 0:
            return "empty file"
    except OSError:
        return ""
    return ""


def scan_stale_candidates(
    repo_root: Path,
    files: Sequence[Path],
    excluded_dirs: Iterable[str],
) -> List[Dict[str, str]]:
    """Find suspicious tracked files that are often stale leftovers."""
    findings: List[Dict[str, str]] = []
    for file_path in files:
        if not file_path.exists():
            continue
        if should_exclude(file_path, repo_root, excluded_dirs):
            continue
        rel_path = str(file_path.relative_to(repo_root))
        reason = classify_stale_candidate(rel_path, file_path)
        if reason:
            findings.append({"path": rel_path, "reason": reason})
    return findings


def repeated_nested_segments(rel_path: str) -> List[str]:
    """Return repeated adjacent path segments, e.g. '.github/.github'."""
    segments = [part for part in Path(rel_path).parts[:-1]]
    duplicates: List[str] = []
    for idx in range(1, len(segments)):
        if segments[idx] == segments[idx - 1]:
            duplicates.append(segments[idx])
    return duplicates


def scan_nested_directory_anomalies(
    repo_root: Path,
    files: Sequence[Path],
    excluded_dirs: Iterable[str],
) -> List[Dict[str, object]]:
    """Detect paths with repeated adjacent directory names."""
    findings: List[Dict[str, object]] = []
    for file_path in files:
        if not file_path.exists():
            continue
        if should_exclude(file_path, repo_root, excluded_dirs):
            continue
        rel_path = str(file_path.relative_to(repo_root))
        duplicates = repeated_nested_segments(rel_path)
        if duplicates:
            findings.append({"path": rel_path, "segments": duplicates})
    return findings


def scan_deep_paths(
    repo_root: Path,
    files: Sequence[Path],
    max_depth: int,
    excluded_dirs: Iterable[str],
) -> List[Dict[str, object]]:
    """Find files with deep nesting beyond max_depth."""
    findings: List[Dict[str, object]] = []
    for file_path in files:
        if not file_path.exists():
            continue
        if should_exclude(file_path, repo_root, excluded_dirs):
            continue
        rel_parts = file_path.relative_to(repo_root).parts
        depth = len(rel_parts) - 1
        if depth > max_depth:
            findings.append({"path": str(Path(*rel_parts)), "depth": depth})
    return findings


def scan_empty_directories(repo_root: Path, excluded_dirs: Iterable[str]) -> List[Dict[str, str]]:
    """Find empty directories that often indicate stale leftovers."""
    findings: List[Dict[str, str]] = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        current = Path(dirpath)

        # Skip excluded directories early and do not descend into them.
        dirnames[:] = [name for name in dirnames if name not in excluded_dirs]

        if current == repo_root:
            continue
        if should_exclude(current, repo_root, excluded_dirs):
            continue

        if not dirnames and not filenames:
            findings.append({"path": str(current.relative_to(repo_root))})

    return findings


def take_limit(items: Sequence[Dict[str, object]], limit: int) -> List[Dict[str, object]]:
    """Limit result count to avoid overwhelming logs."""
    if limit < 0:
        return list(items)
    return list(items[:limit])


def build_report(
    repo_root: Path,
    markers: Sequence[str],
    max_depth: int,
    limit: int,
    excluded_dirs: Iterable[str],
) -> Dict[str, object]:
    """Create a structured hygiene report."""
    files = list_tracked_files(repo_root)
    unfinished = scan_unfinished_markers(repo_root, files, markers, excluded_dirs)
    stale = scan_stale_candidates(repo_root, files, excluded_dirs)
    nested = scan_nested_directory_anomalies(repo_root, files, excluded_dirs)
    deep = scan_deep_paths(repo_root, files, max_depth, excluded_dirs)
    empty_dirs = scan_empty_directories(repo_root, excluded_dirs)

    unfinished_limited = take_limit(unfinished, limit)
    stale_limited = take_limit(stale, limit)
    nested_limited = take_limit(nested, limit)
    deep_limited = take_limit(deep, limit)
    empty_dirs_limited = take_limit(empty_dirs, limit)

    report = {
        "summary": {
            "tracked_files": len(files),
            "unfinished_markers_total": len(unfinished),
            "stale_candidates_total": len(stale),
            "nested_dir_anomalies_total": len(nested),
            "deep_paths_total": len(deep),
            "empty_dirs_total": len(empty_dirs),
            "max_depth": max_depth,
            "limit": limit,
        },
        "unfinished_markers": unfinished_limited,
        "stale_candidates": stale_limited,
        "nested_dir_anomalies": nested_limited,
        "deep_paths": deep_limited,
        "empty_directories": empty_dirs_limited,
    }
    return report


def print_text_report(report: Dict[str, object]) -> None:
    """Print report in readable text format."""
    summary = report["summary"]
    print("=== PF Task: Audit ===")
    print("[*] Repository hygiene report")
    print(f"[*] Tracked files: {summary['tracked_files']}")
    print(f"[*] Unfinished markers: {summary['unfinished_markers_total']}")
    print(f"[*] Stale candidates: {summary['stale_candidates_total']}")
    print(f"[*] Nested directory anomalies: {summary['nested_dir_anomalies_total']}")
    print(f"[*] Deep paths (> {summary['max_depth']}): {summary['deep_paths_total']}")
    print(f"[*] Empty directories: {summary['empty_dirs_total']}")

    sections = [
        ("unfinished_markers", "Unfinished markers"),
        ("stale_candidates", "Stale candidates"),
        ("nested_dir_anomalies", "Nested directory anomalies"),
        ("deep_paths", "Deep paths"),
        ("empty_directories", "Empty directories"),
    ]

    for key, title in sections:
        items = report[key]
        print(f"\n=== {title} ===")
        if not items:
            print("[*] None found")
            continue
        for item in items:
            print(json.dumps(item, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit repository hygiene and unfinished work")
    parser.add_argument(
        "--markers",
        default=",".join(DEFAULT_MARKERS),
        help="Comma-separated unfinished markers to scan for",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum directory depth before reporting a deep path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum findings per category (-1 for no limit)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with status 1 if any findings are present",
    )
    parser.add_argument(
        "--exclude-dirs",
        default="",
        help="Comma-separated directories to exclude in addition to defaults",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    markers = [marker.strip() for marker in args.markers.split(",") if marker.strip()]
    extra_excluded_dirs = {
        directory.strip() for directory in args.exclude_dirs.split(",") if directory.strip()
    }
    excluded_dirs = DEFAULT_EXCLUDED_DIRS | extra_excluded_dirs

    report = build_report(
        repo_root=repo_root,
        markers=markers,
        max_depth=args.max_depth,
        limit=args.limit,
        excluded_dirs=excluded_dirs,
    )

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)

    summary = report["summary"]
    findings_present = any(
        summary[key] > 0
        for key in (
            "unfinished_markers_total",
            "stale_candidates_total",
            "nested_dir_anomalies_total",
            "deep_paths_total",
            "empty_dirs_total",
        )
    )

    if args.fail_on_findings and findings_present:
        print("[!] Findings detected")
        sys.exit(1)

    print("[*] Audit completed")
    sys.exit(0)


if __name__ == "__main__":
    main()
