#!/usr/bin/env python3
"""
PF Task: Repository hygiene checks and safe cleanup.

This task helps keep the repository organized by:
1) Detecting unfinished-code markers in implementation files.
2) Detecting stray backup/temp artifacts.
3) Optionally removing safe-to-delete stray artifacts.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, NamedTuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".java",
    ".rs",
    ".sh",
}

IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "docs",
    "bak",
}

MARKER_TOKEN_PATTERN = r"\b(TODO|FIXME|XXX|HACK|STUB|WIP)\b"
COMMENT_MARKER_PATTERNS = (
    re.compile(rf"#.*{MARKER_TOKEN_PATTERN}"),
    re.compile(rf"//.*{MARKER_TOKEN_PATTERN}"),
    re.compile(rf"/\*.*{MARKER_TOKEN_PATTERN}"),
    re.compile(rf"\*.*{MARKER_TOKEN_PATTERN}"),
)
MARKER_IGNORE_TAG = "hygiene: ignore-marker"

STRAY_EXACT_FILENAMES = {".DS_Store", "Thumbs.db"}
STRAY_ENDINGS = (
    "~HEAD",
    ".orig",
    ".rej",
    ".bak",
    ".tmp",
    "~",
)


class MarkerHit(NamedTuple):
    path: Path
    line_number: int
    line_text: str


def iter_repo_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIR_NAMES]
        root_path = Path(current_root)
        for filename in files:
            yield root_path / filename


def find_unfinished_markers(root: Path) -> List[MarkerHit]:
    hits: List[MarkerHit] = []
    for file_path in iter_repo_files(root):
        if file_path.suffix not in CODE_EXTENSIONS:
            continue

        rel_path = file_path.relative_to(root)
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if line_has_unfinished_marker(line):
                        hits.append(
                            MarkerHit(
                                path=rel_path,
                                line_number=line_number,
                                line_text=line.rstrip(),
                            )
                        )
        except OSError as error:
            print(f"[!] Failed reading {rel_path}: {error}")

    return hits


def line_has_unfinished_marker(line: str) -> bool:
    if MARKER_IGNORE_TAG in line:
        return False
    return any(pattern.search(line) for pattern in COMMENT_MARKER_PATTERNS)


def is_stray_file(file_path: Path) -> bool:
    name = file_path.name
    if name in STRAY_EXACT_FILENAMES:
        return True
    return any(name.endswith(ending) for ending in STRAY_ENDINGS)


def find_stray_files(root: Path) -> List[Path]:
    stray_files: List[Path] = []
    for file_path in iter_repo_files(root):
        if is_stray_file(file_path):
            stray_files.append(file_path.relative_to(root))
    return sorted(stray_files)


def delete_stray_files(root: Path, stray_files: Iterable[Path]) -> List[Path]:
    removed: List[Path] = []
    for rel_path in stray_files:
        abs_path = root / rel_path
        try:
            abs_path.unlink(missing_ok=True)
            removed.append(rel_path)
        except OSError as error:
            print(f"[!] Failed removing {rel_path}: {error}")
    return removed


def print_marker_report(marker_hits: List[MarkerHit]) -> None:
    if not marker_hits:
        print("[✓] No unfinished markers found in implementation files.")
        return

    print(f"[!] Found {len(marker_hits)} unfinished marker(s):")
    for hit in marker_hits:
        print(f"    - {hit.path}:{hit.line_number}: {hit.line_text}")


def print_stray_report(stray_files: List[Path]) -> None:
    if not stray_files:
        print("[✓] No stray backup/temp files found.")
        return

    print(f"[!] Found {len(stray_files)} stray backup/temp file(s):")
    for rel_path in stray_files:
        print(f"    - {rel_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run repository hygiene checks and optional safe cleanup."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Delete detected stray backup/temp files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=== PF Task: Hygiene ===")
    print(f"[*] Project root: {PROJECT_ROOT}")

    marker_hits = find_unfinished_markers(PROJECT_ROOT)
    stray_files = find_stray_files(PROJECT_ROOT)

    print_marker_report(marker_hits)
    print_stray_report(stray_files)

    if args.fix and stray_files:
        print("[*] Removing stray files...")
        removed = delete_stray_files(PROJECT_ROOT, stray_files)
        for rel_path in removed:
            print(f"    [✓] Removed {rel_path}")
        stray_files = find_stray_files(PROJECT_ROOT)
        if not stray_files:
            print("[✓] Stray-file cleanup complete.")

    has_failures = bool(marker_hits or stray_files)
    if has_failures:
        print("[!] Hygiene checks reported issues.")
        return 1

    print("[✓] Hygiene checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
