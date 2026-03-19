"""
Architecture analysis functionality for Amazon Q integration.

This module provides architecture, dependency, and design pattern analysis.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
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

        structure_score = structure_analysis.get('structure_score', 60)
        pattern_score = pattern_analysis.get('design_score', 60)
        dependency_count = dependency_analysis.get('dependency_count', 0)
        dependency_hygiene_score = max(40, 100 - max(0, dependency_count - 20))
        architecture_score = int(
            max(
                0,
                min(
                    100,
                    (structure_score * 0.45)
                    + (pattern_score * 0.40)
                    + (dependency_hygiene_score * 0.15)
                )
            )
        )
        
        return {
            'structure': structure_analysis,
            'dependencies': dependency_analysis,
            'patterns': pattern_analysis,
            'architecture_score': architecture_score,
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'amazon_q_architecture_local'
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

        excluded_dirs = {'.git', '__pycache__', 'node_modules', 'dist', 'build', '.venv', 'venv'}
        has_src = (repo_path_obj / 'src').exists()
        has_docs = (repo_path_obj / 'docs').exists()
        has_tests = (repo_path_obj / 'tests').exists()

        for root, dirs, files in os.walk(repo_path_obj):
            dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('.')]
            for file_name in files:
                if file_name.startswith('.'):
                    continue
                file_path = Path(root) / file_name
                total_files += 1
                ext = file_path.suffix.lower()
                file_counts[ext] = file_counts.get(ext, 0) + 1
        
        # Check for common project files
        has_readme = any((repo_path_obj / name).exists() for name in ['README.md', 'README.txt', 'README'])
        has_license = any((repo_path_obj / name).exists() for name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md'])
        has_gitignore = (repo_path_obj / '.gitignore').exists()
        has_requirements = any((repo_path_obj / name).exists() for name in ['requirements.txt', 'package.json', 'Pipfile'])

        structure_score = 40
        if has_readme:
            structure_score += 15
        if has_license:
            structure_score += 10
        if has_gitignore:
            structure_score += 10
        if has_requirements:
            structure_score += 10
        if has_src:
            structure_score += 5
        if has_docs:
            structure_score += 5
        if has_tests:
            structure_score += 5
        
        return {
            'total_files': total_files,
            'file_types': file_counts,
            'has_readme': has_readme,
            'has_license': has_license,
            'has_gitignore': has_gitignore,
            'has_requirements': has_requirements,
            'has_src': has_src,
            'has_docs': has_docs,
            'has_tests': has_tests,
            'structure_score': max(0, min(100, structure_score))
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
        patterns_found: List[Dict[str, Any]] = []

        pattern_indicators = {
            'singleton': ['class.*Singleton', '__new__.*cls'],
            'factory': ['class.*Factory', 'def create_'],
            'observer': ['class.*Observer', 'def notify'],
            'strategy': ['class.*Strategy', 'def execute'],
            'decorator': ['@.*decorator', 'def wrapper'],
            'adapter': ['class.*Adapter', 'def adapt'],
            'facade': ['class.*Facade', 'def simplify']
        }

        seen: Set[Tuple[str, str]] = set()

        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern_name, indicators in pattern_indicators.items():
                    for indicator in indicators:
                        if re.search(indicator, content, re.IGNORECASE):
                            if (pattern_name, file_path) in seen:
                                continue
                            seen.add((pattern_name, file_path))
                            patterns_found.append({
                                'pattern': pattern_name,
                                'file': file_path,
                                'confidence': 'medium' if len(indicators) > 1 else 'low'
                            })
                            break
                            
            except Exception as e:
                logger.warning(f"Failed to analyze patterns in {file_path}: {e}")
        unique_patterns = sorted(set(p['pattern'] for p in patterns_found))
        pattern_diversity = len(unique_patterns)
        design_score = min(95, 55 + (pattern_diversity * 6))

        return {
            'patterns_detected': patterns_found,
            'unique_patterns': unique_patterns,
            'pattern_diversity': pattern_diversity,
            'design_score': design_score
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze design patterns: {e}")
        return {'error': str(e)}
