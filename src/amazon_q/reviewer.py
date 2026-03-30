"""
Main Amazon Q Reviewer class.

This module provides the primary interface for Amazon Q code review functionality.
"""

import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from .security_scanner import perform_security_scan
from .quality_analyzer import analyze_code_quality
from .architecture_analyzer import analyze_architecture
from .utils import calculate_overall_score, generate_recommendations

logger = logging.getLogger(__name__)


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AmazonQReviewer:
    """
    Amazon Q Developer integration for automated code review.
    
    This class provides methods to perform code reviews using Amazon Q services,
    with fallback to mock implementation when AWS services are unavailable.
    """
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize Amazon Q reviewer.
        
        Args:
            region: AWS region for service calls (default: us-east-1)
        """
        self.region = region
        self.session = None
        self.codewhisperer_client = None
        self.bedrock_client = None
        self._availability_checked = False
        self._is_available = False
        
        # Initialize AWS session if credentials are available
        self._initialize_aws_session()
    
    def _initialize_aws_session(self) -> None:
        """Initialize AWS session and clients."""
        try:
            # Create AWS session
            self.session = boto3.Session(region_name=self.region)
            
            # Initialize CodeWhisperer client (for security scanning)
            self.codewhisperer_client = self.session.client('codewhisperer')
            
            # Initialize Bedrock client (for AI-powered analysis)
            self.bedrock_client = self.session.client('bedrock-runtime')
            
            logger.info("AWS session initialized successfully")
            
        except (NoCredentialsError, ClientError) as e:
            logger.warning(f"AWS credentials not available or invalid: {e}")
            self.session = None
            self.codewhisperer_client = None
            self.bedrock_client = None
        except Exception as e:
            logger.error(f"Failed to initialize AWS session: {e}")
            self.session = None
            self.codewhisperer_client = None
            self.bedrock_client = None
    
    def is_available(self) -> bool:
        """
        Check if Amazon Q services are available.
        
        Returns:
            True if AWS services are configured and accessible, False otherwise
        """
        if self._availability_checked:
            return self._is_available
        
        if not self.session:
            self._is_available = False
            self._availability_checked = True
            return False
        
        try:
            # Test AWS connectivity with a simple STS call
            sts_client = self.session.client('sts')
            sts_client.get_caller_identity()
            
            self._is_available = True
            logger.info("Amazon Q services are available")
            
        except Exception as e:
            logger.warning(f"Amazon Q services not available: {e}")
            self._is_available = False
        
        self._availability_checked = True
        return self._is_available
    
    def review_repository(self, repo_path: str, custom_rules: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Perform comprehensive code review using Amazon Q services.
        
        Args:
            repo_path: Path to the repository to review
            custom_rules: Optional custom review rules configuration
            
        Returns:
            Dictionary containing review results and recommendations
        """
        # Import mock implementation locally to avoid circular import
        # (mock_reviewer imports from this module's parent package)
        from .mock_reviewer import mock_review
        
        if not self.is_available():
            logger.warning("Amazon Q services not available, falling back to mock review")
            return mock_review(repo_path, custom_rules)
        
        try:
            logger.info(f"Starting Amazon Q review for repository: {repo_path}")
            
            # Perform security scan with CodeWhisperer
            security_results = perform_security_scan(repo_path, self.codewhisperer_client)
            
            # Perform code quality analysis
            quality_results = analyze_code_quality(repo_path, custom_rules, self.bedrock_client)
            
            # Perform architecture review
            architecture_results = analyze_architecture(repo_path)
            
            # Combine results
            review_results = {
                'timestamp': _timestamp_utc(),
                'repository_path': repo_path,
                'service_used': 'amazon_q',
                'security_analysis': security_results,
                'code_quality': quality_results,
                'architecture_review': architecture_results,
                'overall_score': calculate_overall_score(
                    security_results, quality_results, architecture_results
                ),
                'recommendations': generate_recommendations(
                    security_results, quality_results, architecture_results
                )
            }
            
            logger.info("Amazon Q review completed successfully")
            return review_results
            
        except Exception as e:
            logger.error(f"Amazon Q review failed: {e}")
            logger.info("Falling back to mock review")
            return mock_review(repo_path, custom_rules)
