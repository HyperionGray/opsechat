"""
Architecture analysis functionality for Amazon Q integration.

This module provides architecture, dependency, and design pattern analysis.
"""

import json
import logging
import re
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
        # Analyze project structure
        structure_analysis = analyze_project_structure(repo_path)

        # Analyze dependencies
        dependency_analysis = analyze_dependencies(repo_path)

        # Analyze design patterns
        pattern_analysis = analyze_design_patterns(repo_path)

        architecture_score = _calculate_architecture_score(
            structure_analysis, dependency_analysis, pattern_analysis
        )

        return {
            'structure': structure_analysis,
            'dependencies': dependency_analysis,
            'patterns': pattern_analysis,
            'architecture_score': architecture_score,
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'amazon_q_architecture'
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

        # Count different types of files
        file_counts: Dict[str, int] = {}
        total_files = 0
        directory_depths: List[int] = []
        repeated_directory_names: List[str] = []

        for file_path in repo_path_obj.rglob('*'):
            if _is_skipped_path(file_path):
                continue
            if file_path.is_dir():
                depth = len(file_path.relative_to(repo_path_obj).parts)
                directory_depths.append(depth)
                parts = file_path.relative_to(repo_path_obj).parts
                if len(parts) > 1 and parts[-1] == parts[-2]:
                    repeated_directory_names.append(str(file_path))
                continue
            if file_path.is_file():
                total_files += 1
                ext = file_path.suffix.lower() or '<no_extension>'
                file_counts[ext] = file_counts.get(ext, 0) + 1

        # Check for common project files
        has_readme = any((repo_path_obj / name).exists() for name in ['README.md', 'README.txt', 'README'])
        has_license = any((repo_path_obj / name).exists() for name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md'])
        has_gitignore = (repo_path_obj / '.gitignore').exists()
        has_requirements = any((repo_path_obj / name).exists() for name in ['requirements.txt', 'package.json', 'Pipfile'])

        common_dirs = ('src', 'tests', 'docs', 'scripts', '.github')
        present_common_dirs = [name for name in common_dirs if (repo_path_obj / name).exists()]
        max_depth = max(directory_depths, default=1)
        structure_score = _calculate_structure_score(
            has_readme=has_readme,
            has_license=has_license,
            has_gitignore=has_gitignore,
            has_requirements=has_requirements,
            present_common_dir_count=len(present_common_dirs),
            max_depth=max_depth,
            repeated_dir_count=len(repeated_directory_names),
        )

        return {
            'total_files': total_files,
            'file_types': file_counts,
            'has_readme': has_readme,
            'has_license': has_license,
            'has_gitignore': has_gitignore,
            'has_requirements': has_requirements,
            'common_directories': present_common_dirs,
            'max_directory_depth': max_depth,
            'repeated_directory_paths': repeated_directory_names[:20],
            'structure_score': structure_score,
        }

    except Exception as e:
        logger.error(f"Failed to analyze project structure: {e}")
        return {'error': str(e)}


def analyze_dependencies(repo_path: str) -> Dict[str, Any]:
    """Analyze project dependencies."""
    try:
        repo_path_obj = Path(repo_path)
        dependencies: Dict[str, Any] = {}
        dependency_health = {
            'python': {'total': 0, 'pinned': 0, 'unpinned': 0},
            'nodejs': {'dependencies': 0, 'devDependencies': 0},
        }

        # Check Python dependencies
        requirements_file = repo_path_obj / 'requirements.txt'
        if requirements_file.exists():
            with open(requirements_file, 'r') as f:
                python_deps = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            dependencies['python'] = python_deps
            for dep in python_deps:
                if dep.startswith(('-r', '--')):
                    continue
                dependency_health['python']['total'] += 1
                if _is_pinned_python_dependency(dep):
                    dependency_health['python']['pinned'] += 1
                else:
                    dependency_health['python']['unpinned'] += 1

        # Check Node.js dependencies
        package_json = repo_path_obj / 'package.json'
        if package_json.exists():
            with open(package_json, 'r') as f:
                package_data = json.load(f)
            dependencies['nodejs'] = {
                'dependencies': package_data.get('dependencies', {}),
                'devDependencies': package_data.get('devDependencies', {})
            }
            dependency_health['nodejs']['dependencies'] = len(
                dependencies['nodejs'].get('dependencies', {})
            )
            dependency_health['nodejs']['devDependencies'] = len(
                dependencies['nodejs'].get('devDependencies', {})
            )

        # Calculate dependency count
        dep_count = 0
        for deps in dependencies.values():
            if isinstance(deps, list):
                dep_count += len(deps)
            else:
                dep_count += len(deps.get('dependencies', {}))
                dep_count += len(deps.get('devDependencies', {}))

        has_lockfile = any(
            (repo_path_obj / name).exists() for name in ['package-lock.json', 'yarn.lock', 'Pipfile.lock', 'poetry.lock']
        )
        dependency_score = _calculate_dependency_score(dependency_health, has_lockfile)

        return {
            'dependencies': dependencies,
            'dependency_count': dep_count,
            'has_lockfile': has_lockfile,
            'dependency_health': dependency_health,
            'dependency_score': dependency_score,
        }

    except Exception as e:
        logger.error(f"Failed to analyze dependencies: {e}")
        return {'error': str(e)}


def analyze_design_patterns(repo_path: str) -> Dict[str, Any]:
    """Analyze design patterns used in the codebase."""
    try:
        source_files = [path for path in get_source_files(repo_path) if _is_analyzable_source(path)]
        patterns_found: Dict[str, List[Dict[str, str]]] = {}

        pattern_indicators = {
            'singleton': [r'class\s+\w*Singleton\b', r'def\s+__new__\s*\(.*cls'],
            'factory': [r'class\s+\w*Factory\b', r'def\s+create_\w+\s*\('],
            'observer': [r'class\s+\w*Observer\b', r'def\s+notify\w*\s*\('],
            'strategy': [r'class\s+\w*Strategy\b', r'def\s+execute\w*\s*\('],
            'decorator': [r'@\w+', r'def\s+wrapper\s*\('],
            'dependency_injection': [r'__init__\s*\(.*\w+\s*:\s*\w+', r'def\s+\w+\(.*service.*\)'],
            'flask_blueprint': [r'Blueprint\s*\(', r'register_blueprint\s*\('],
        }

        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                for pattern_name, indicators in pattern_indicators.items():
                    for indicator in indicators:
                        if re.search(indicator, content, re.IGNORECASE):
                            patterns_found.setdefault(pattern_name, []).append({
                                'file': file_path,
                                'indicator': indicator,
                                'confidence': 'medium',
                            })
                            break

            except Exception as e:
                logger.warning(f"Failed to analyze patterns in {file_path}: {e}")

        flattened_patterns = []
        for pattern_name, evidence in patterns_found.items():
            unique_files = sorted({entry['file'] for entry in evidence})
            flattened_patterns.append({
                'pattern': pattern_name,
                'occurrences': len(evidence),
                'files': unique_files[:15],
                'confidence': 'medium',
            })

        pattern_diversity = len(patterns_found)
        total_occurrences = sum(len(entries) for entries in patterns_found.values())
        design_score = _calculate_design_score(pattern_diversity, total_occurrences)

        return {
            'patterns_detected': flattened_patterns,
            'pattern_diversity': pattern_diversity,
            'total_pattern_occurrences': total_occurrences,
            'design_score': design_score,
        }

    except Exception as e:
        logger.error(f"Failed to analyze design patterns: {e}")
        return {'error': str(e)}


def _calculate_structure_score(
    has_readme: bool,
    has_license: bool,
    has_gitignore: bool,
    has_requirements: bool,
    present_common_dir_count: int,
    max_depth: int,
    repeated_dir_count: int,
) -> int:
    """Calculate structure score from repository organization signals."""
    score = 0
    score += 20 if has_readme else 0
    score += 10 if has_license else 0
    score += 10 if has_gitignore else 0
    score += 10 if has_requirements else 0
    score += min(25, present_common_dir_count * 5)

    depth_penalty = max(0, max_depth - 6) * 3
    repetition_penalty = min(15, repeated_dir_count * 2)
    score = score + 25 - depth_penalty - repetition_penalty
    return max(0, min(100, score))


def _calculate_dependency_score(dependency_health: Dict[str, Dict[str, int]], has_lockfile: bool) -> int:
    """Calculate dependency management score."""
    py_total = dependency_health.get('python', {}).get('total', 0)
    py_unpinned = dependency_health.get('python', {}).get('unpinned', 0)
    node_total = (
        dependency_health.get('nodejs', {}).get('dependencies', 0)
        + dependency_health.get('nodejs', {}).get('devDependencies', 0)
    )

    score = 100
    if py_total > 0:
        unpinned_ratio = py_unpinned / max(1, py_total)
        score -= int(unpinned_ratio * 35)

    if node_total > 40:
        # Large dependency trees increase upgrade and supply-chain surface area.
        score -= min(15, (node_total - 40) // 5)

    if not has_lockfile:
        score -= 20

    return max(0, min(100, score))


def _calculate_design_score(pattern_diversity: int, total_occurrences: int) -> int:
    """Score design maturity based on pattern diversity and practical usage evidence."""
    base_score = 55
    diversity_bonus = min(30, pattern_diversity * 6)
    usage_bonus = min(15, total_occurrences * 2)
    return max(0, min(100, base_score + diversity_bonus + usage_bonus))


def _calculate_architecture_score(
    structure_analysis: Dict[str, Any],
    dependency_analysis: Dict[str, Any],
    pattern_analysis: Dict[str, Any],
) -> int:
    """Compute weighted architecture score."""
    structure_score = structure_analysis.get('structure_score', 0)
    dependency_score = dependency_analysis.get('dependency_score', 0)
    design_score = pattern_analysis.get('design_score', 0)

    score = (structure_score * 0.45) + (dependency_score * 0.25) + (design_score * 0.30)
    return int(max(0, min(100, score)))


def _is_pinned_python_dependency(requirement: str) -> bool:
    """Return True when requirement appears version-pinned."""
    return '==' in requirement or '@' in requirement


def _is_skipped_path(path: Path) -> bool:
    """Skip hidden and generated paths during repository structure analysis."""
    path_text = str(path).replace('\\', '/')
    if '/.git/' in path_text:
        return True
    if '/node_modules/' in path_text or '/__pycache__/' in path_text:
        return True
    return any(part.startswith('.') for part in path.parts)


def _is_analyzable_source(file_path: str) -> bool:
    """Skip vendored/minified/generated source files for pattern analysis."""
    normalized = file_path.replace('\\', '/').lower()
    file_name = Path(file_path).name.lower()
    if any(marker in normalized for marker in ('/node_modules/', '/bak/', '/dist/', '/build/')):
        return False
    if '.min.' in file_name:
        return False
    return True
