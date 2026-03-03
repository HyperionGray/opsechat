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
        
        return {
            'structure': structure_analysis,
            'dependencies': dependency_analysis,
            'patterns': pattern_analysis,
            'architecture_score': 88,  # Placeholder
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
        
        return {
            'total_files': total_files,
            'file_types': file_counts,
            'has_readme': has_readme,
            'has_license': has_license,
            'has_gitignore': has_gitignore,
            'has_requirements': has_requirements,
            'structure_score': 85 if all([has_readme, has_license, has_gitignore, has_requirements]) else 60
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
        
        return {
            'dependencies': dependencies,
            'dependency_count': sum(len(deps) if isinstance(deps, list) else len(deps.get('dependencies', {})) + len(deps.get('devDependencies', {})) for deps in dependencies.values()),
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
