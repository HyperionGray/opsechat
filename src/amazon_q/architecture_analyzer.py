"""
Architecture analysis functionality for Amazon Q integration.

This module provides architecture, dependency, and design pattern analysis.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from .utils import get_source_files

logger = logging.getLogger(__name__)


def clamp_score(value: float) -> int:
    """Clamp score values to a consistent 0-100 range."""
    return max(0, min(100, int(round(value))))


def calculate_architecture_score(
    structure_analysis: Dict[str, Any],
    dependency_analysis: Dict[str, Any],
    pattern_analysis: Dict[str, Any],
) -> int:
    """
    Build an aggregate architecture score from sub-analysis outputs.

    Weighting:
      - Structure hygiene: 45%
      - Dependency hygiene: 25%
      - Design pattern signals: 30%
    """
    structure_score = structure_analysis.get('structure_score', 55)
    design_score = pattern_analysis.get('design_score', 60)
    dependency_count = dependency_analysis.get('dependency_count', 0)
    has_lockfile = dependency_analysis.get('has_lockfile', False)

    # Dependency score favors reproducible builds and manageable dependency size.
    dependency_score = 92
    if dependency_count == 0:
        dependency_score -= 12
    elif dependency_count > 150:
        dependency_score -= 40
    elif dependency_count > 80:
        dependency_score -= 28
    elif dependency_count > 40:
        dependency_score -= 18
    elif dependency_count > 20:
        dependency_score -= 10

    if dependency_count > 0 and not has_lockfile:
        dependency_score -= 15

    weighted_score = (
        structure_score * 0.45 +
        clamp_score(dependency_score) * 0.25 +
        design_score * 0.30
    )
    return clamp_score(weighted_score)


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
        architecture_score = calculate_architecture_score(
            structure_analysis,
            dependency_analysis,
            pattern_analysis,
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
        file_counts = {}
        total_files = 0
        
        for file_path in repo_path_obj.rglob('*'):
            if file_path.is_file():
                total_files += 1
                ext = file_path.suffix.lower()
                file_counts[ext] = file_counts.get(ext, 0) + 1
        
        # Check for common project files
        has_readme = any((repo_path_obj / name).exists() for name in ['README.md', 'README.txt', 'README'])
        has_license = any((repo_path_obj / name).exists() for name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md'])
        has_gitignore = (repo_path_obj / '.gitignore').exists()
        has_requirements = any((repo_path_obj / name).exists() for name in ['requirements.txt', 'package.json', 'Pipfile'])
        
        checklist_score = (
            int(has_readme) +
            int(has_license) +
            int(has_gitignore) +
            int(has_requirements)
        )
        hygiene_component = (checklist_score / 4) * 55
        diversity_component = min(25, len(file_counts) * 3)
        size_component = min(20, total_files * 2)

        return {
            'total_files': total_files,
            'file_types': file_counts,
            'has_readme': has_readme,
            'has_license': has_license,
            'has_gitignore': has_gitignore,
            'has_requirements': has_requirements,
            'structure_score': clamp_score(
                hygiene_component + diversity_component + size_component
            ),
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
        
        return {
            'dependencies': dependencies,
            'dependency_count': dep_count,
            'has_lockfile': any((repo_path_obj / name).exists() for name in ['package-lock.json', 'yarn.lock', 'Pipfile.lock'])
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze dependencies: {e}")
        return {'error': str(e)}


def analyze_design_patterns(repo_path: str) -> Dict[str, Any]:
    """Analyze design patterns used in the codebase."""
    try:
        source_files = get_source_files(repo_path)
        patterns_found = []
        
        # Simple pattern detection (placeholder for real analysis)
        pattern_indicators = {
            'singleton': ['class.*Singleton', '__new__.*cls'],
            'factory': ['class.*Factory', 'def create_'],
            'observer': ['class.*Observer', 'def notify'],
            'strategy': ['class.*Strategy', 'def execute'],
            'decorator': ['@.*decorator', 'def wrapper']
        }
        
        for file_path in source_files[:10]:  # Limit for demo
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern_name, indicators in pattern_indicators.items():
                    for indicator in indicators:
                        if re.search(indicator, content, re.IGNORECASE):
                            patterns_found.append({
                                'pattern': pattern_name,
                                'file': file_path,
                                'confidence': 'medium'
                            })
                            break
                            
            except Exception as e:
                logger.warning(f"Failed to analyze patterns in {file_path}: {e}")
        
        return {
            'patterns_detected': patterns_found,
            'pattern_diversity': len(set(p['pattern'] for p in patterns_found)),
            'design_score': min(90, 60 + len(set(p['pattern'] for p in patterns_found)) * 5)
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze design patterns: {e}")
        return {'error': str(e)}
