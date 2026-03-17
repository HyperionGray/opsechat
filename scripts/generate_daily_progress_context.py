#!/usr/bin/env python3
"""Generate daily progress context for workflow issues.

This script scans the repository for:
- Unfinished markers in source-like files (TODO/FIXME/STUB/TBD)
- Potential cleanup candidates (backup/deprecated/temp artifacts)

It prints a markdown report to stdout for use in GitHub issue bodies.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|STUB|TBD)\b", re.IGNORECASE)
CLEANUP_FILE_PATTERN = re.compile(
    r"(backup|deprecated|obsolete|legacy|_old|old_|_tmp|tmp_|\.bak$)",
    re.IGNORECASE,
)

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".java",
    ".rs",
    ".sh",
    ".yml",
    ".yaml",
}

SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    "playwright-report",
    "test-results",
}

SKIP_MARKER_ROOTS = {
    "docs",
    "bak",
}


@dataclass
class MarkerMatch:
    path: Path
    line_number: int
    marker: str
    line: str


def should_skip_path(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(part in SKIP_DIRECTORIES for part in parts)


def scan_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_path(path, root):
            continue
        if path.suffix.lower() in SOURCE_EXTENSIONS:
            yield path


def collect_marker_matches(root: Path) -> list[MarkerMatch]:
    matches: list[MarkerMatch] = []
    for path in scan_source_files(root):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in SKIP_MARKER_ROOTS:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for i, line in enumerate(lines, start=1):
            for marker in MARKER_PATTERN.findall(line):
                matches.append(
                    MarkerMatch(path=rel, line_number=i, marker=marker.upper(), line=line.strip())
                )
    return matches


def collect_cleanup_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_path(path, root):
            continue
        rel = path.relative_to(root)

        if CLEANUP_FILE_PATTERN.search(path.name):
            candidates.append(rel)
            continue

        if ".github" in rel.parts and "workflows" in rel.parts and "backup" in path.stem.lower():
            candidates.append(rel)
    return sorted(set(candidates))


def render_report(root: Path, max_items: int) -> str:
    marker_matches = collect_marker_matches(root)
    cleanup_candidates = collect_cleanup_candidates(root)

    marker_counts = Counter(match.marker for match in marker_matches)
    file_counts = Counter(str(match.path) for match in marker_matches)
    by_file: dict[str, list[MarkerMatch]] = defaultdict(list)
    for match in marker_matches:
        by_file[str(match.path)].append(match)

    lines: list[str] = []
    lines.append("### Automated Repository Context")
    lines.append("")
    lines.append("#### Unfinished markers in code")
    lines.append(f"- Total markers found: **{len(marker_matches)}**")
    if marker_counts:
        for marker, count in sorted(marker_counts.items()):
            lines.append(f"- {marker}: {count}")
    else:
        lines.append("- No unfinished markers found in scanned source files.")
    lines.append("")

    lines.append("#### Top files needing attention")
    if file_counts:
        for file_path, count in file_counts.most_common(max_items):
            lines.append(f"- `{file_path}`: {count} marker(s)")
            for match in by_file[file_path][:2]:
                lines.append(
                    f"  - L{match.line_number} ({match.marker}): `{match.line[:120]}`"
                )
    else:
        lines.append("- No files with unfinished markers found.")
    lines.append("")

    lines.append("#### Potential cleanup candidates")
    if cleanup_candidates:
        for candidate in cleanup_candidates[:max_items]:
            lines.append(f"- `{candidate}`")
    else:
        lines.append("- No obvious cleanup candidate filenames found.")
    lines.append("")

    lines.append("#### Suggested focus")
    lines.append("1. Resolve real code-level unfinished markers before doc-only backlog items.")
    lines.append("2. Remove or archive stale backup/deprecated files that are no longer referenced.")
    lines.append("3. Prefer one incremental feature plus a small cleanup in each daily iteration.")

    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily progress context markdown.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to analyze (default: current directory).",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Maximum items per section (default: 10).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    report = render_report(root=root, max_items=max(1, args.max_items))
    print(report, end="")


if __name__ == "__main__":
    main()
