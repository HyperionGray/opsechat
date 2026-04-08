#!/usr/bin/env python3
"""
Workflow hygiene checker.

Validates that repository workflows stay aligned with template policy:
1. Workflow files under .github/workflows are either template-backed
   or explicitly allowlisted as local-only.
2. Required template workflows are present in both templates and active workflows.
3. No nested ".github/.github/workflows" directory exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HygieneResult:
    unmanaged_workflows: list[str]
    missing_required_in_templates: list[str]
    missing_required_in_workflows: list[str]
    nested_workflow_entries: list[str]

    @property
    def ok(self) -> bool:
        return not (
            self.unmanaged_workflows
            or self.missing_required_in_templates
            or self.missing_required_in_workflows
            or self.nested_workflow_entries
        )


def _load_policy(policy_path: Path) -> dict[str, Any]:
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    with policy_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    allowed_local = data.get("allowed_local_workflows", [])
    required_template = data.get("required_template_workflows", [])

    if not isinstance(allowed_local, list) or not all(
        isinstance(item, str) for item in allowed_local
    ):
        raise ValueError("Policy key 'allowed_local_workflows' must be a list of strings")

    if not isinstance(required_template, list) or not all(
        isinstance(item, str) for item in required_template
    ):
        raise ValueError(
            "Policy key 'required_template_workflows' must be a list of strings"
        )

    return {
        "allowed_local_workflows": set(allowed_local),
        "required_template_workflows": set(required_template),
    }


def _collect_workflow_names(directory: Path) -> set[str]:
    if not directory.exists():
        return set()

    names: set[str] = set()
    for pattern in ("*.yml", "*.yaml"):
        for path in directory.glob(pattern):
            if path.is_file():
                names.add(path.name)
    return names


def check_workflow_hygiene(repo_root: Path, policy_path: Path) -> HygieneResult:
    policy = _load_policy(policy_path)

    templates_dir = repo_root / ".github" / "workflow-templates"
    workflows_dir = repo_root / ".github" / "workflows"
    nested_dir = repo_root / ".github" / ".github" / "workflows"

    template_workflows = _collect_workflow_names(templates_dir)
    active_workflows = _collect_workflow_names(workflows_dir)

    allowed_local = policy["allowed_local_workflows"]
    required_template = policy["required_template_workflows"]

    unmanaged = sorted(
        name
        for name in active_workflows
        if name not in template_workflows and name not in allowed_local
    )

    missing_required_in_templates = sorted(
        name for name in required_template if name not in template_workflows
    )
    missing_required_in_workflows = sorted(
        name for name in required_template if name not in active_workflows
    )

    nested_entries = (
        sorted(str(path.relative_to(repo_root)) for path in nested_dir.glob("*"))
        if nested_dir.exists()
        else []
    )

    return HygieneResult(
        unmanaged_workflows=unmanaged,
        missing_required_in_templates=missing_required_in_templates,
        missing_required_in_workflows=missing_required_in_workflows,
        nested_workflow_entries=nested_entries,
    )


def _render_failure(result: HygieneResult) -> str:
    lines: list[str] = ["Workflow hygiene check failed:"]

    if result.unmanaged_workflows:
        lines.append("  Unmanaged workflow files in .github/workflows:")
        lines.extend(f"    - {name}" for name in result.unmanaged_workflows)
        lines.append(
            "  Action: either add matching template, or allowlist in .github/workflow-hygiene.json"
        )

    if result.missing_required_in_templates:
        lines.append("  Required template workflows missing from .github/workflow-templates:")
        lines.extend(f"    - {name}" for name in result.missing_required_in_templates)

    if result.missing_required_in_workflows:
        lines.append("  Required workflows missing from .github/workflows:")
        lines.extend(f"    - {name}" for name in result.missing_required_in_workflows)

    if result.nested_workflow_entries:
        lines.append("  Nested workflow placeholder files detected (cleanup required):")
        lines.extend(f"    - {entry}" for entry in result.nested_workflow_entries)

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GitHub workflow hygiene")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    parser.add_argument(
        "--policy",
        default=".github/workflow-hygiene.json",
        help="Path to workflow hygiene policy JSON file",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = (repo_root / policy_path).resolve()

    try:
        result = check_workflow_hygiene(repo_root, policy_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Workflow hygiene check error: {exc}", file=sys.stderr)
        return 2

    if result.ok:
        print("Workflow hygiene check passed.")
        return 0

    print(_render_failure(result), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
