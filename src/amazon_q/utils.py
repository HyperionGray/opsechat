"""
Utility functions for Amazon Q integration.
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def get_source_files(repo_path: str) -> List[str]:
    """Get list of source code files in the repository."""
    source_files = []
    extensions = {'.py', '.js', '.ts', '.java', '.go', '.cpp', '.c', '.h', '.hpp'}
    
    try:
        repo_path_obj = Path(repo_path)
        for file_path in repo_path_obj.rglob('*'):
            if (file_path.is_file() and 
                file_path.suffix in extensions and
                not any(part.startswith('.') for part in file_path.parts) and
                'node_modules' not in str(file_path) and
                '__pycache__' not in str(file_path)):
                source_files.append(str(file_path))
    except Exception as e:
        logger.error(f"Failed to get source files: {e}")
    
    return source_files


def calculate_overall_score(security_results: dict, quality_results: dict, architecture_results: dict) -> int:
    """Calculate overall code quality score."""
    try:
        # Weight different aspects
        security_weight = 0.4
        quality_weight = 0.4
        architecture_weight = 0.2
        
        # Extract scores (with defaults)
        security_score = 100 - (security_results.get('vulnerabilities_found', 0) * 10)
        security_score = max(0, min(100, security_score))
        
        quality_score = quality_results.get('metrics', {}).get('maintainability_score', 75)
        architecture_score = architecture_results.get('architecture_score', 75)
        
        overall = (security_score * security_weight + 
                  quality_score * quality_weight + 
                  architecture_score * architecture_weight)
        
        return int(overall)
        
    except Exception as e:
        logger.error(f"Failed to calculate overall score: {e}")
        return 75  # Default score


def generate_recommendations(security_results: dict, quality_results: dict, architecture_results: dict) -> List[dict]:
    """Generate actionable recommendations based on analysis results."""
    recommendations = []
    
    try:
        # Security recommendations
        vuln_count = security_results.get('vulnerabilities_found', 0)
        if vuln_count > 0:
            recommendations.append({
                'category': 'security',
                'priority': 'high',
                'title': f'Address {vuln_count} security vulnerabilities',
                'description': 'Review and fix identified security issues to improve code safety',
                'action_items': [
                    'Review security scan results',
                    'Fix hardcoded credentials if found',
                    'Validate input sanitization',
                    'Update vulnerable dependencies'
                ]
            })
        
        # Quality recommendations
        quality_issues = quality_results.get('issues', [])
        if len(quality_issues) > 5:
            recommendations.append({
                'category': 'code_quality',
                'priority': 'medium',
                'title': 'Improve code quality',
                'description': f'Address {len(quality_issues)} code quality issues',
                'action_items': [
                    'Break down long functions',
                    'Add missing documentation',
                    'Improve code organization',
                    'Add unit tests where needed'
                ]
            })
        
        # Architecture recommendations
        arch_score = architecture_results.get('architecture_score', 75)
        if arch_score < 80:
            recommendations.append({
                'category': 'architecture',
                'priority': 'low',
                'title': 'Enhance software architecture',
                'description': 'Improve design patterns and code organization',
                'action_items': [
                    'Review design patterns usage',
                    'Improve separation of concerns',
                    'Consider refactoring for better maintainability',
                    'Add architectural documentation'
                ]
            })
        
        # General recommendations
        if not recommendations:
            recommendations.append({
                'category': 'general',
                'priority': 'low',
                'title': 'Maintain code quality',
                'description': 'Code quality is good, continue following best practices',
                'action_items': [
                    'Keep dependencies updated',
                    'Maintain test coverage',
                    'Regular security reviews',
                    'Monitor performance metrics'
                ]
            })
        
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        recommendations.append({
            'category': 'error',
            'priority': 'medium',
            'title': 'Review generation failed',
            'description': 'Unable to generate specific recommendations',
            'action_items': ['Check Amazon Q integration configuration']
        })
    
    return recommendations
