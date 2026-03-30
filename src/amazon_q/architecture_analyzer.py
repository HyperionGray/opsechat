"""
Architecture analysis functionality for Amazon Q integration.

This module provides deterministic architecture, dependency, and design-pattern
analysis that can run without AWS-managed analysis services.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .utils import get_source_files

logger = logging.getLogger(__name__)

CORE_DIRS = {"src", "tests", "docs", "templates", "static"}
KNOWN_ANTI_PATTERNS = [
    ("god_module", re.compile(r"(?i)^.{1400,}$", re.DOTALL), "Very large file may need decomposition"),
    ("direct_sys_path_mutation", re.compile(r"sys\.path\.insert\s*\("), "Runtime import-path mutation"),
]


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def analyze_architecture(repo_path: str) -> Dict[str, Any]:
    """
    Analyze software architecture and design patterns.

    Args:
        repo_path: Path to repository

    Returns:
        Architecture analysis results
    """
    try:
        structure_analysis = analyze_project_structure(repo_path)
        dependency_analysis = analyze_dependencies(repo_path)
        pattern_analysis = analyze_design_patterns(repo_path)

        anti_pattern_count = len(pattern_analysis.get("anti_patterns_detected", []))
        structure_score = structure_analysis.get("structure_score", 60)
        dependency_health = dependency_analysis.get("dependency_health_score", 70)
        design_score = pattern_analysis.get("design_score", 65)
        architecture_score = _safe_score(
            (structure_score * 0.40) + (dependency_health * 0.25) + (design_score * 0.35) - anti_pattern_count * 2
        )

        return {
            "structure": structure_analysis,
            "dependencies": dependency_analysis,
            "patterns": pattern_analysis,
            "architecture_score": architecture_score,
            "analysis_timestamp": _timestamp_utc(),
            "analyzer": "local_static_architecture_analyzer",
        }
    except Exception as exc:
        logger.error("Architecture analysis failed: %s", exc)
        return {
            "structure": {},
            "dependencies": {},
            "patterns": {},
            "architecture_score": 0,
            "analysis_timestamp": _timestamp_utc(),
            "analyzer": "error",
            "error": str(exc),
        }


def analyze_project_structure(repo_path: str) -> Dict[str, Any]:
    """Analyze project structure and organization."""
    try:
        repo_path_obj = Path(repo_path)
        file_counts: Dict[str, int] = {}
        total_files = 0

        ignored_dirs = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv"}
        top_level_dirs = {p.name for p in repo_path_obj.iterdir() if p.is_dir() and p.name not in ignored_dirs}

        for file_path in repo_path_obj.rglob("*"):
            if file_path.is_dir():
                if file_path.name in ignored_dirs:
                    continue
                continue
            if any(part in ignored_dirs for part in file_path.parts):
                continue
            total_files += 1
            ext = file_path.suffix.lower() or "<no_ext>"
            file_counts[ext] = file_counts.get(ext, 0) + 1

        has_readme = any((repo_path_obj / name).exists() for name in ["README.md", "README.txt", "README"])
        has_license = any((repo_path_obj / name).exists() for name in ["LICENSE", "LICENSE.txt", "LICENSE.md"])
        has_gitignore = (repo_path_obj / ".gitignore").exists()
        has_requirements = any(
            (repo_path_obj / name).exists() for name in ["requirements.txt", "package.json", "Pipfile"]
        )
        has_version = (repo_path_obj / "VERSION").exists()

        missing_core_dirs = sorted(d for d in CORE_DIRS if d not in top_level_dirs)
        structure_score = 100
        if not has_readme:
            structure_score -= 12
        if not has_license:
            structure_score -= 8
        if not has_gitignore:
            structure_score -= 8
        if not has_requirements:
            structure_score -= 8
        if not has_version:
            structure_score -= 5
        structure_score -= min(20, len(missing_core_dirs) * 4)
        structure_score = max(0, structure_score)

        return {
            "total_files": total_files,
            "file_types": file_counts,
            "has_readme": has_readme,
            "has_license": has_license,
            "has_gitignore": has_gitignore,
            "has_requirements": has_requirements,
            "has_version": has_version,
            "top_level_directories": sorted(top_level_dirs),
            "missing_core_directories": missing_core_dirs,
            "structure_score": structure_score,
        }
    except Exception as exc:
        logger.error("Failed to analyze project structure: %s", exc)
        return {"error": str(exc)}


def analyze_dependencies(repo_path: str) -> Dict[str, Any]:
    """Analyze project dependencies."""
    try:
        repo_path_obj = Path(repo_path)
        dependencies: Dict[str, Any] = {}
        dependency_count = 0

        requirements_file = repo_path_obj / "requirements.txt"
        if requirements_file.exists():
            with open(requirements_file, "r", encoding="utf-8", errors="ignore") as file_handle:
                python_deps = [
                    line.strip()
                    for line in file_handle
                    if line.strip() and not line.strip().startswith("#")
                ]
            dependencies["python"] = python_deps
            dependency_count += len(python_deps)

        package_json = repo_path_obj / "package.json"
        if package_json.exists():
            with open(package_json, "r", encoding="utf-8", errors="ignore") as file_handle:
                package_data = json.load(file_handle)
            js_deps = package_data.get("dependencies", {})
            js_dev_deps = package_data.get("devDependencies", {})
            dependencies["nodejs"] = {
                "dependencies": js_deps,
                "devDependencies": js_dev_deps,
            }
            dependency_count += len(js_deps) + len(js_dev_deps)

        has_lockfile = any(
            (repo_path_obj / name).exists()
            for name in ["package-lock.json", "yarn.lock", "Pipfile.lock", "poetry.lock"]
        )
        dependency_health_score = 100
        if not dependencies:
            dependency_health_score -= 35
        if dependencies and not has_lockfile:
            dependency_health_score -= 20
        if dependency_count > 150:
            dependency_health_score -= 20
        elif dependency_count > 80:
            dependency_health_score -= 10
        dependency_health_score = max(0, dependency_health_score)

        return {
            "dependencies": dependencies,
            "dependency_count": dependency_count,
            "has_lockfile": has_lockfile,
            "dependency_health_score": dependency_health_score,
        }
    except Exception as exc:
        logger.error("Failed to analyze dependencies: %s", exc)
        return {"error": str(exc)}


def analyze_design_patterns(repo_path: str) -> Dict[str, Any]:
    """Analyze design patterns used in the codebase."""
    try:
        source_files = sorted(get_source_files(repo_path))
        patterns_found: List[Dict[str, Any]] = []
        anti_patterns_found: List[Dict[str, Any]] = []

        pattern_indicators = {
            "singleton": [r"class\s+\w*Singleton", r"__new__\s*\(\s*cls"],
            "factory": [r"class\s+\w*Factory", r"def\s+create_[A-Za-z0-9_]*\s*\("],
            "observer": [r"class\s+\w*Observer", r"def\s+notify[A-Za-z0-9_]*\s*\("],
            "strategy": [r"class\s+\w*Strategy", r"def\s+execute[A-Za-z0-9_]*\s*\("],
            "decorator": [r"@\w+", r"def\s+wrapper\s*\("],
            "dataclass": [r"@dataclass"],
        }

        for file_path in source_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                    content = file_handle.read()

                for pattern_name, indicators in pattern_indicators.items():
                    if any(re.search(indicator, content, re.IGNORECASE) for indicator in indicators):
                        patterns_found.append(
                            {
                                "pattern": pattern_name,
                                "file": file_path,
                                "confidence": "medium",
                            }
                        )

                for anti_name, anti_pattern, description in KNOWN_ANTI_PATTERNS:
                    if anti_pattern.search(content):
                        anti_patterns_found.append(
                            {
                                "type": anti_name,
                                "file": file_path,
                                "description": description,
                            }
                        )
            except Exception as exc:
                logger.warning("Failed to analyze patterns in %s: %s", file_path, exc)

        unique_patterns = sorted({entry["pattern"] for entry in patterns_found})
        pattern_diversity = len(unique_patterns)
        anti_pattern_penalty = min(25, len(anti_patterns_found) * 4)
        design_score = _safe_score(62 + pattern_diversity * 6 - anti_pattern_penalty)

        return {
            "patterns_detected": patterns_found,
            "pattern_types_detected": unique_patterns,
            "pattern_diversity": pattern_diversity,
            "anti_patterns_detected": anti_patterns_found,
            "design_score": design_score,
        }
    except Exception as exc:
        logger.error("Failed to analyze design patterns: %s", exc)
        return {"error": str(exc)}
