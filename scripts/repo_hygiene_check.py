#!/usr/bin/env python3
"""
Repository hygiene checks for docs and tracked artifacts.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

# Root markdown files that are intentionally kept at repository root.
ALLOWED_ROOT_MARKDOWN = {
    "README.md",
    "QUICKSTART.md",
    "SECURITY.md",
    "LICENSE.md",
    "START_HERE.md",
    "DEVELOPER_QUICKSTART.md",
    "TODO.md",
}

# Root convenience symlinks and their expected targets.
EXPECTED_SYMLINKS = {
    "compose-up.sh": "scripts/compose-up.sh",
    "compose-down.sh": "scripts/compose-down.sh",
    "verify-setup.sh": "scripts/verify-setup.sh",
    "install-quadlets.sh": "scripts/install-quadlets.sh",
    "Dockerfile": "containers/Dockerfile",
    "docker-compose.yml": "container-compose.yml",
    "torrc": "containers/torrc",
}

STALE_GLOBS = (
    "**/*~HEAD",
    "**/*.orig",
    "**/*.rej",
)


def iter_markdown_files(repo_root: Path) -> list[Path]:
    docs_files = list((repo_root / "docs").glob("**/*.md"))
    root_files = [path for path in repo_root.glob("*.md")]
    return sorted(docs_files + root_files)


def _normalize_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if "#" in target:
        target = target.split("#", 1)[0]
    if "?" in target:
        target = target.split("?", 1)[0]
    return target


def _is_external_link(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
        or lowered.startswith("#")
    )


def check_markdown_links(repo_root: Path) -> list[str]:
    issues: list[str] = []
    for markdown_file in iter_markdown_files(repo_root):
        text = markdown_file.read_text(encoding="utf-8", errors="ignore")
        for match in LINK_PATTERN.finditer(text):
            raw_target = match.group(1)
            target = _normalize_link_target(raw_target)
            if not target or _is_external_link(target):
                continue

            resolved = (markdown_file.parent / target).resolve()
            if not resolved.exists():
                rel_source = markdown_file.relative_to(repo_root)
                issues.append(
                    f"broken link in {rel_source}: {raw_target}"
                )
    return issues


def check_root_markdown_placement(repo_root: Path) -> list[str]:
    issues: list[str] = []
    for file_path in sorted(repo_root.glob("*.md")):
        if file_path.name not in ALLOWED_ROOT_MARKDOWN:
            issues.append(f"root markdown should move to docs/: {file_path.name}")
    return issues


def check_stale_artifacts(repo_root: Path) -> list[str]:
    issues: list[str] = []
    for pattern in STALE_GLOBS:
        for path in repo_root.glob(pattern):
            if ".git" in path.parts:
                continue
            rel_path = path.relative_to(repo_root)
            issues.append(f"stale artifact present: {rel_path}")
    return sorted(set(issues))


def check_expected_symlinks(repo_root: Path) -> list[str]:
    issues: list[str] = []
    for name, target in EXPECTED_SYMLINKS.items():
        path = repo_root / name
        if not path.exists() and not path.is_symlink():
            issues.append(f"missing convenience path: {name}")
            continue

        if not path.is_symlink():
            issues.append(f"expected symlink but found regular file: {name}")
            continue

        actual_target = path.readlink().as_posix()
        if actual_target != target:
            issues.append(
                f"symlink target mismatch for {name}: expected {target}, got {actual_target}"
            )
    return issues


def run_checks(repo_root: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    warnings.extend(check_markdown_links(repo_root))
    failures.extend(check_root_markdown_placement(repo_root))
    failures.extend(check_stale_artifacts(repo_root))
    failures.extend(check_expected_symlinks(repo_root))
    return warnings, failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate documentation links and repository hygiene."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat markdown link warnings as failures.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    warnings, failures = run_checks(repo_root)

    print("=== Repository Hygiene Check ===")
    print(f"Repository root: {repo_root}")
    print(f"Warnings: {len(warnings)}")
    print(f"Failures: {len(failures)}")

    if warnings:
        for warning in warnings:
            print(f"[WARN] {warning}")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")

    if args.strict and warnings:
        return 1

    if failures:
        return 1

    print("[OK] No hygiene issues detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
