"""
Architecture analysis functionality for Amazon Q integration.

This module provides architecture, dependency, and design pattern analysis.
"""

import json
import logging
import re
from datetime import datetime, timezone
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
            structure_score=structure_analysis.get('structure_score', 0),
            dependency_score=dependency_analysis.get('dependency_health_score', 0),
            design_score=pattern_analysis.get('design_score', 0),
        )
        
        return {
            'structure': structure_analysis,
            'dependencies': dependency_analysis,
            'patterns': pattern_analysis,
            'architecture_score': architecture_score,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
            'analyzer': 'local_heuristic_architecture'
        }
        
    except Exception as e:
        logger.error(f"Architecture analysis failed: {e}")
        return {
            'structure': {},
            'dependencies': {},
            'patterns': {},
            'architecture_score': 0,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
            'analyzer': 'error',
            'error': str(e)
        }


def analyze_project_structure(repo_path: str) -> Dict[str, Any]:
    """Analyze project structure and organization."""
    try:
        repo_path_obj = Path(repo_path)
        
        # Count different types of files
        file_counts = {}
        total_files = 0
        
        for file_path in repo_path_obj.rglob('*'):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(repo_path_obj))
                if _is_ignored_path(rel_path):
                    continue
                total_files += 1
                ext = file_path.suffix.lower()
                file_counts[ext] = file_counts.get(ext, 0) + 1
        
        # Check for common project files
        has_readme = any((repo_path_obj / name).exists() for name in ['README.md', 'README.txt', 'README'])
        has_license = any((repo_path_obj / name).exists() for name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md'])
        has_gitignore = (repo_path_obj / '.gitignore').exists()
        has_requirements = any((repo_path_obj / name).exists() for name in ['requirements.txt', 'package.json', 'Pipfile'])
        
        docs_count = sum(1 for path in (repo_path_obj / 'docs').rglob('*.md')) if (repo_path_obj / 'docs').exists() else 0
        src_dir_exists = (repo_path_obj / 'src').exists()
        tests_dir_exists = (repo_path_obj / 'tests').exists()

        structure_score = _calculate_structure_score(
            total_files=total_files,
            has_readme=has_readme,
            has_license=has_license,
            has_gitignore=has_gitignore,
            has_requirements=has_requirements,
            docs_count=docs_count,
            src_dir_exists=src_dir_exists,
            tests_dir_exists=tests_dir_exists,
        )

        return {
            'total_files': total_files,
            'file_types': file_counts,
            'has_readme': has_readme,
            'has_license': has_license,
            'has_gitignore': has_gitignore,
            'has_requirements': has_requirements,
            'docs_markdown_files': docs_count,
            'has_src_dir': src_dir_exists,
            'has_tests_dir': tests_dir_exists,
            'structure_score': structure_score,
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze project structure: {e}")
        return {'error': str(e)}


def analyze_dependencies(repo_path: str) -> Dict[str, Any]:
    """Analyze project dependencies."""
    try:
        repo_path_obj = Path(repo_path)
        dependencies = {}
        
        # Check Python dependencies
        requirements_file = repo_path_obj / 'requirements.txt'
        if requirements_file.exists():
            with open(requirements_file, 'r') as f:
                python_deps = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            dependencies['python'] = python_deps
        
        # Check Node.js dependencies
        package_json = repo_path_obj / 'package.json'
        if package_json.exists():
            with open(package_json, 'r') as f:
                package_data = json.load(f)
            dependencies['nodejs'] = {
                'dependencies': package_data.get('dependencies', {}),
                'devDependencies': package_data.get('devDependencies', {})
            }
        
        # Calculate dependency count
        dep_count = 0
        for deps in dependencies.values():
            if isinstance(deps, list):
                dep_count += len(deps)
            else:
                dep_count += len(deps.get('dependencies', {}))
                dep_count += len(deps.get('devDependencies', {}))
        
        has_lockfile = any((repo_path_obj / name).exists() for name in ['package-lock.json', 'yarn.lock', 'Pipfile.lock'])
        dependency_health_score = _calculate_dependency_health_score(dep_count, has_lockfile)

        return {
            'dependencies': dependencies,
            'dependency_count': dep_count,
            'has_lockfile': has_lockfile,
            'dependency_health_score': dependency_health_score,
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze dependencies: {e}")
        return {'error': str(e)}


def analyze_design_patterns(repo_path: str) -> Dict[str, Any]:
    """Analyze design patterns used in the codebase."""
    try:
        source_files = get_source_files(repo_path)
        patterns_found = []
        
        pattern_indicators = {
            'singleton': [r'class\s+\w*Singleton', r'def\s+__new__\s*\(.*cls'],
            'factory': [r'class\s+\w*Factory', r'def\s+create_\w+'],
            'observer': [r'class\s+\w*Observer', r'def\s+notify'],
            'strategy': [r'class\s+\w*Strategy', r'def\s+execute'],
            'decorator': [r'@\w+', r'def\s+wrapper'],
            'repository': [r'class\s+\w*Repository', r'def\s+save\w*\('],
        }
        
        for file_path in source_files:
            if _is_ignored_path(file_path):
                continue
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern_name, indicators in pattern_indicators.items():
                    for indicator in indicators:
                        if re.search(indicator, content, re.IGNORECASE):
                            patterns_found.append({
                                'pattern': pattern_name,
                                'file': file_path,
                                'confidence': _calculate_pattern_confidence(content, indicators),
                            })
                            break
                            
            except Exception as e:
                logger.warning(f"Failed to analyze patterns in {file_path}: {e}")
        
        unique_patterns = sorted(set(p['pattern'] for p in patterns_found))
        design_score = min(100, 45 + len(unique_patterns) * 10)
        
        return {
            'patterns_detected': patterns_found,
            'pattern_diversity': len(unique_patterns),
            'unique_patterns': unique_patterns,
            'design_score': design_score,
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze design patterns: {e}")
        return {'error': str(e)}


def _calculate_structure_score(
    total_files: int,
    has_readme: bool,
    has_license: bool,
    has_gitignore: bool,
    has_requirements: bool,
    docs_count: int,
    src_dir_exists: bool,
    tests_dir_exists: bool,
) -> int:
    score = 40
    score += 12 if has_readme else 0
    score += 8 if has_license else 0
    score += 8 if has_gitignore else 0
    score += 10 if has_requirements else 0
    score += 8 if docs_count > 0 else 0
    score += 7 if src_dir_exists else 0
    score += 7 if tests_dir_exists else 0

    if total_files > 3000:
        score -= 8
    elif total_files > 1500:
        score -= 4

    return max(0, min(100, score))


def _calculate_dependency_health_score(dependency_count: int, has_lockfile: bool) -> int:
    score = 75
    if dependency_count == 0:
        score = 55
    elif dependency_count <= 20:
        score = 90
    elif dependency_count <= 60:
        score = 80
    elif dependency_count <= 120:
        score = 70
    else:
        score = 60

    if has_lockfile:
        score += 5
    return max(0, min(100, score))


def _calculate_architecture_score(structure_score: int, dependency_score: int, design_score: int) -> int:
    weighted = (structure_score * 0.45) + (dependency_score * 0.25) + (design_score * 0.30)
    return int(round(max(0, min(100, weighted))))


def _calculate_pattern_confidence(content: str, indicators: List[str]) -> str:
    hits = 0
    for indicator in indicators:
        if re.search(indicator, content, re.IGNORECASE):
            hits += 1
    if hits >= 2:
        return 'high'
    if hits == 1:
        return 'medium'
    return 'low'


def _is_ignored_path(file_path: str) -> bool:
    lowered = file_path.lower().replace('\\', '/')
    ignored_segments = ['/node_modules/', '/.git/', '/__pycache__/', '/.venv/', '/bak/']
    if lowered.endswith('.min.js'):
        return True
    return any(segment in f"/{lowered}" for segment in ignored_segments)
