#!/usr/bin/env python3
"""
Summarize recent repository direction and hygiene signals.

This script is designed for automation workflows. It inspects recent commits,
highlights where work is concentrated, suggests practical next steps, and flags
basic structure problems such as nested .github metadata directories.
"""

from __future__ import annotations

import argparse
import subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


Commit = Tuple[str, str]
FocusSummary = List[Tuple[str, int]]


def run_git(args: Sequence[str]) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def get_recent_commits(limit: int) -> List[Commit]:
    """Return recent commits as (sha, subject)."""
    output = run_git(["log", f"-n{limit}", "--pretty=format:%H%x1f%s"])
    commits: List[Commit] = []

    for line in output.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        sha = sha.strip()
        subject = subject.strip()
        if sha and subject:
            commits.append((sha, subject))
    return commits


def get_files_for_commit(sha: str) -> List[str]:
    """Return changed files for a commit SHA."""
    output = run_git(["show", "--pretty=format:", "--name-only", sha])
    return [line.strip() for line in output.splitlines() if line.strip()]


def top_level_area(path: str) -> str:
    """Map a path to its top-level area."""
    if "/" not in path:
        return "root"
    first = path.split("/", 1)[0].strip()
    return first or "root"


def summarize_focus(paths: Iterable[str], limit: int = 5) -> FocusSummary:
    """Summarize top areas touched by recent commits."""
    counts = Counter(top_level_area(path) for path in paths if path)
    return counts.most_common(limit)


def find_hygiene_warnings(paths: Iterable[str]) -> List[str]:
    """Detect basic repository hygiene issues."""
    warnings: List[str] = []

    if Path(".github/.github").exists():
        warnings.append(
            "Nested '.github/.github' directory detected; keep workflows under '.github/workflows/' only."
        )

    nested_paths = sorted(path for path in set(paths) if path.startswith(".github/.github/"))
    if nested_paths:
        warnings.append(
            "Recent commits touched nested '.github/.github/*' paths; these are often stale or confusing."
        )

    return warnings


def suggest_next_steps(focus: FocusSummary, warnings: Iterable[str]) -> List[str]:
    """Generate practical next steps from focus areas and warnings."""
    steps: List[str] = []
    warning_list = list(warnings)

    for warning in warning_list:
        steps.append(f"Resolve hygiene warning: {warning}")

    area_guidance = {
        ".github": "Strengthen workflow reliability with tighter triggers and clearer automation prompts.",
        "tests": "Add regression tests for recent behavior changes before expanding feature scope.",
        "docs": "Update docs to match current behavior and remove stale references.",
        "scripts": "Harden utility scripts with input validation and deterministic output.",
        "src": "Continue modularization in src/ and expand focused unit test coverage.",
    }

    for area, _count in focus:
        suggestion = area_guidance.get(area)
        if suggestion and suggestion not in steps:
            steps.append(suggestion)
        if len(steps) >= 4:
            break

    if not steps:
        steps.append("Pick one small user-facing improvement and ship it with matching tests and docs.")

    return steps[:4]


def render_markdown(commits: List[Commit], focus: FocusSummary, warnings: List[str], steps: List[str]) -> str:
    """Render the final markdown summary."""
    lines: List[str] = []
    lines.append("## Repository Direction Summary")
    lines.append("")

    if commits:
        lines.append("### Recent commits")
        for sha, subject in commits:
            lines.append(f"- `{sha[:7]}` {subject}")
    else:
        lines.append("- No recent commits found.")
    lines.append("")

    if focus:
        lines.append("### Hot areas (recently touched)")
        for area, count in focus:
            lines.append(f"- `{area}` ({count} file changes)")
    else:
        lines.append("- No changed files found in the inspected commit window.")
    lines.append("")

    lines.append("### Suggested next steps")
    for step in steps:
        lines.append(f"- {step}")
    lines.append("")

    if warnings:
        lines.append("### Hygiene warnings")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_summary(limit: int) -> str:
    """Build repository direction markdown."""
    commits = get_recent_commits(limit)

    changed_files: List[str] = []
    for sha, _subject in commits:
        changed_files.extend(get_files_for_commit(sha))

    focus = summarize_focus(changed_files)
    warnings = find_hygiene_warnings(changed_files)
    steps = suggest_next_steps(focus, warnings)
    return render_markdown(commits, focus, warnings, steps)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize recent repository direction.")
    parser.add_argument("--limit", type=int, default=8, help="Number of recent commits to inspect")
    args = parser.parse_args()

    try:
        print(build_summary(limit=max(1, args.limit)), end="")
    except subprocess.CalledProcessError as exc:
        error_message = exc.stderr.strip() if exc.stderr else str(exc)
        print("## Repository Direction Summary")
        print("")
        print(f"- Failed to gather git history: {error_message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
