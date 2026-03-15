#!/usr/bin/env python3
"""
Amazon Q Code Review Integration Module - Backward Compatibility Wrapper

This module provides backward compatibility for the refactored Amazon Q integration.
The actual implementation has been split into modular components in src/amazon_q/.

For new code, please import directly from src.amazon_q:
    from src.amazon_q import AmazonQReviewer

This wrapper maintains compatibility with existing code that imports:
    from amazon_q_integration import AmazonQReviewer
"""

import os
import json
import sys
import logging

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import from the new modular structure
from amazon_q import AmazonQReviewer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def main():
    """Command-line interface for Amazon Q code review."""
    if len(sys.argv) != 2:
        print("Usage: python amazon_q_integration.py <repository_path>")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    
    if not os.path.exists(repo_path):
        print(f"Error: Repository path '{repo_path}' does not exist")
        sys.exit(1)
    
    # Initialize reviewer
    reviewer = AmazonQReviewer()
    
    # Perform review
    print(f"Starting Amazon Q code review for: {repo_path}")
    print(f"AWS services available: {reviewer.is_available()}")
    
    results = reviewer.review_repository(repo_path)
    
    # Display results summary
    print("\n" + "="*80)
    print("Amazon Q Code Review Results")
    print("="*80)
    print(f"Repository: {results.get('repository_path', 'N/A')}")
    print(f"Service: {results.get('service_used', 'N/A')}")
    print(f"Overall Score: {results.get('overall_score', 0)}/100")
    print(f"Mock Mode: {results.get('mock_mode', False)}")
    
    if 'security_analysis' in results:
        sec = results['security_analysis']
        print(f"\nSecurity: {sec.get('total_files_scanned', 0)} files scanned, "
              f"{sec.get('vulnerabilities_found', 0)} vulnerabilities found")
    
    if 'code_quality' in results:
        qual = results['code_quality']
        metrics = qual.get('metrics', {})
        print(f"Quality: Maintainability {metrics.get('maintainability_score', 0)}/100, "
              f"Complexity {metrics.get('complexity_score', 0)}/100")
    
    if 'recommendations' in results and results['recommendations']:
        print(f"\nRecommendations ({len(results['recommendations'])}):")
        for i, rec in enumerate(results['recommendations'][:3], 1):
            print(f"  {i}. [{rec.get('priority', 'N/A').upper()}] {rec.get('title', 'N/A')}")
    
    print("="*80)
    
    # Save results to file
    output_file = "amazon_q_review_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    main()

