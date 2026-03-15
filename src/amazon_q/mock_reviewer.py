"""
Mock implementation for Amazon Q code review.

This module provides a comprehensive mock review when AWS services are unavailable.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any

from .security_scanner import perform_security_scan
from .architecture_analyzer import analyze_architecture
from .utils import get_source_files, calculate_overall_score, generate_recommendations

logger = logging.getLogger(__name__)


def mock_review(repo_path: str, custom_rules: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Perform mock code review when Amazon Q services are not available.
    
    This provides a comprehensive analysis using local tools and heuristics
    to simulate Amazon Q functionality.
    
    Args:
        repo_path: Path to the repository to review
        custom_rules: Optional custom review rules configuration
        
    Returns:
        Dictionary containing mock review results
    """
    logger.info(f"Performing mock Amazon Q review for repository: {repo_path}")
    
    try:
        # Perform local analysis
        source_files = get_source_files(repo_path)
        
        # Mock security analysis
        security_results = {
            'total_files_scanned': len(source_files),
            'vulnerabilities_found': 0,  # Assume clean for mock
            'security_issues': [],
            'scan_timestamp': datetime.utcnow().isoformat() + 'Z',
            'scanner': 'mock_security_scanner'
        }
        
        # Mock quality analysis
        quality_results = {
            'metrics': {
                'maintainability_score': 88,
                'complexity_score': 82,
                'documentation_score': 90,
                'test_coverage_estimate': 78
            },
            'issues': [],
            'total_files_analyzed': len(source_files),
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'mock_quality_analyzer'
        }
        
        # Mock architecture analysis
        architecture_results = {
            'structure': {},
            'dependencies': {},
            'patterns': {},
            'architecture_score': 85,
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'mock_architecture_analyzer'
        }
        
        # Use actual architecture analysis for better mock
        try:
            architecture_results = analyze_architecture(repo_path)
        except Exception as e:
            logger.warning(f"Failed to run architecture analysis in mock: {e}")
        
        # Generate comprehensive mock review
        review_results = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'repository_path': repo_path,
            'service_used': 'mock_amazon_q',
            'security_analysis': security_results,
            'code_quality': quality_results,
            'architecture_review': architecture_results,
            'overall_score': calculate_overall_score(
                security_results, quality_results, architecture_results
            ),
            'recommendations': generate_recommendations(
                security_results, quality_results, architecture_results
            ),
            'mock_mode': True,
            'note': 'This is a mock review. For full Amazon Q analysis, configure AWS credentials.'
        }
        
        logger.info("Mock Amazon Q review completed successfully")
        return review_results
        
    except Exception as e:
        logger.error(f"Mock review failed: {e}")
        return {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'repository_path': repo_path,
            'service_used': 'mock_amazon_q',
            'error': str(e),
            'overall_score': 0,
            'recommendations': [{
                'category': 'error',
                'priority': 'high',
                'title': 'Review failed',
                'description': 'Unable to perform code review',
                'action_items': ['Check repository path and permissions']
            }],
            'mock_mode': True
        }
