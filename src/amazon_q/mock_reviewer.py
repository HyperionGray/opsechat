"""
Mock implementation for Amazon Q code review.

This module provides a comprehensive mock review when AWS services are unavailable.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from .quality_analyzer import analyze_code_quality
from .security_scanner import perform_security_scan
from .architecture_analyzer import analyze_architecture
from .utils import calculate_overall_score, generate_recommendations

logger = logging.getLogger(__name__)


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
        # Use the same local analyzers in mock mode to keep results realistic and
        # deterministic even when AWS services are unavailable.
        security_results = perform_security_scan(repo_path, codewhisperer_client=None)
        quality_results = analyze_code_quality(repo_path, custom_rules=custom_rules, bedrock_client=None)
        architecture_results = analyze_architecture(repo_path)
        
        # Generate comprehensive mock review
        review_results = {
            'timestamp': _timestamp_utc(),
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
            'timestamp': _timestamp_utc(),
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
