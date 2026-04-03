"""
Architecture analysis functionality for Amazon Q integration.

This module provides deterministic architecture, dependency, and design pattern
analysis that can run locally without cloud APIs.
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .utils import get_source_files

logger = logging.getLogger(__name__)


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

        structure_score = structure_analysis.get('structure_score', 0)
        dependency_score = dependency_analysis.get('dependency_score', 0)
        design_score = pattern_analysis.get('design_score', 0)
        architecture_score = _clamp_score(int(round(
            structure_score * 0.45 + dependency_score * 0.25 + design_score * 0.30
        )))

        return {
            'structure': structure_analysis,
            'dependencies': dependency_analysis,
            'patterns': pattern_analysis,
            'architecture_score': architecture_score,
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'amazon_q_local_architecture',
        }

    except Exception as e:
        logger.error(f"Architecture analysis failed: {e}")
        return {
            'structure': {},
            'dependencies': {},
            'patterns': {},
            'architecture_score': 0,
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'error',
            'error': str(e)
        }


def analyze_project_structure(repo_path: str) -> Dict[str, Any]:
    """Analyze project structure and organization."""
    try:
        repo_path_obj = Path(repo_path)

        file_counts: Dict[str, int] = {}
        total_files = 0
        max_depth = 0

        excluded_parts = {'.git', 'node_modules', '__pycache__', '.venv'}
        for file_path in repo_path_obj.rglob('*'):
            if not file_path.is_file():
                continue
            rel_parts = set(file_path.relative_to(repo_path_obj).parts)
            if rel_parts.intersection(excluded_parts):
                continue
            total_files += 1
            depth = len(file_path.relative_to(repo_path_obj).parts) - 1
            max_depth = max(max_depth, depth)
            ext = file_path.suffix.lower() or '<no_ext>'
            file_counts[ext] = file_counts.get(ext, 0) + 1

        has_readme = any((repo_path_obj / name).exists() for name in ['README.md', 'README.txt', 'README'])
        has_license = any((repo_path_obj / name).exists() for name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md'])
        has_gitignore = (repo_path_obj / '.gitignore').exists()
        has_requirements = any((repo_path_obj / name).exists() for name in ['requirements.txt', 'package.json', 'Pipfile'])

        key_dir_names = ['src', 'docs', 'tests', 'scripts']
        key_dirs_present = {name: (repo_path_obj / name).exists() for name in key_dir_names}
        key_dirs_count = sum(1 for present in key_dirs_present.values() if present)

        # Penalize very deep trees and reward common top-level organization.
        structure_score = _clamp_score(
            45 +
            (10 if has_readme else 0) +
            (10 if has_license else 0) +
            (8 if has_gitignore else 0) +
            (12 if has_requirements else 0) +
            (key_dirs_count * 4) -
            max(0, max_depth - 6) * 2
        )

        top_file_types = dict(
            Counter(file_counts).most_common(10)
        )

        return {
            'total_files': total_files,
            'file_types': top_file_types,
            'has_readme': has_readme,
            'has_license': has_license,
            'has_gitignore': has_gitignore,
            'has_requirements': has_requirements,
            'key_directories': key_dirs_present,
            'max_directory_depth': max_depth,
            'structure_score': structure_score,
        }

    except Exception as e:
        logger.error(f"Failed to analyze project structure: {e}")
        return {'error': str(e), 'structure_score': 0}


def analyze_dependencies(repo_path: str) -> Dict[str, Any]:
    """Analyze project dependencies."""
    try:
        repo_path_obj = Path(repo_path)
        dependencies: Dict[str, Any] = {}

        requirements_file = repo_path_obj / 'requirements.txt'
        if requirements_file.exists():
            python_deps = []
            for raw_line in requirements_file.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                python_deps.append(line)
            dependencies['python'] = python_deps

        package_json = repo_path_obj / 'package.json'
        if package_json.exists():
            package_data = json.loads(package_json.read_text(encoding='utf-8', errors='ignore'))
            dependencies['nodejs'] = {
                'dependencies': package_data.get('dependencies', {}),
                'devDependencies': package_data.get('devDependencies', {})
            }

        dep_count = 0
        runtime_dep_count = 0
        for ecosystem, deps in dependencies.items():
            if isinstance(deps, list):
                dep_count += len(deps)
                runtime_dep_count += len(deps)
            elif ecosystem == 'nodejs':
                runtime = deps.get('dependencies', {})
                dev = deps.get('devDependencies', {})
                runtime_dep_count += len(runtime)
                dep_count += len(runtime) + len(dev)

        has_lockfile = any((repo_path_obj / name).exists() for name in ['package-lock.json', 'yarn.lock', 'Pipfile.lock'])
        dependency_score = _clamp_score(
            65 +
            (10 if has_lockfile else -8) +
            (8 if runtime_dep_count > 0 else -12) -
            max(0, dep_count - 80) // 4
        )

        return {
            'dependencies': dependencies,
            'dependency_count': dep_count,
            'runtime_dependency_count': runtime_dep_count,
            'has_lockfile': has_lockfile,
            'dependency_score': dependency_score,
        }

    except Exception as e:
        logger.error(f"Failed to analyze dependencies: {e}")
        return {'error': str(e), 'dependency_score': 0}


def analyze_design_patterns(repo_path: str) -> Dict[str, Any]:
    """Analyze design patterns used in the codebase."""
    try:
        source_files = sorted(get_source_files(repo_path))
        patterns_found = []

        pattern_indicators = {
            'singleton': [r'class\s+\w*Singleton\b', r'__new__\s*\(.*cls'],
            'factory': [r'class\s+\w*Factory\b', r'def\s+create_\w+\('],
            'observer': [r'class\s+\w*Observer\b', r'def\s+notify(_\w+)?\('],
            'strategy': [r'class\s+\w*Strategy\b', r'def\s+execute\('],
            'decorator': [r'@\w+', r'def\s+wrapper\('],
        }

        for file_path in source_files:
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
                for pattern_name, indicators in pattern_indicators.items():
                    hits = sum(
                        len(re.findall(indicator, content, re.IGNORECASE | re.MULTILINE))
                        for indicator in indicators
                    )
                    if hits:
                        patterns_found.append({
                            'pattern': pattern_name,
                            'file': file_path,
                            'confidence': _confidence_from_hits(hits),
                            'hits': hits,
                        })
            except Exception as e:
                logger.warning(f"Failed to analyze patterns in {file_path}: {e}")

        pattern_types = {item['pattern'] for item in patterns_found}
        design_score = _clamp_score(int(round(
            50 +
            min(len(pattern_types), 6) * 7 +
            min(len(patterns_found), 30) * 1.2
        )))

        return {
            'patterns_detected': patterns_found,
            'pattern_diversity': len(pattern_types),
            'design_score': design_score,
        }

    except Exception as e:
        logger.error(f"Failed to analyze design patterns: {e}")
        return {'error': str(e), 'design_score': 0}


def _confidence_from_hits(hits: int) -> str:
    if hits >= 4:
        return 'high'
    if hits >= 2:
        return 'medium'
    return 'low'


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))
