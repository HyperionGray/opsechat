#!/usr/bin/env python3
"""
Amazon Q Integration Test Script

This script tests the Amazon Q code review integration to ensure it's working correctly.
It can be used to validate the setup and troubleshoot any issues.

Usage:
    python test_amazon_q_integration.py [--verbose] [--mock-only]

Options:
    --verbose    Enable verbose logging
    --mock-only  Only test mock mode (skip AWS services)
"""

import os
import sys
import json
import argparse
import tempfile
from pathlib import Path

# Add the current directory to Python path to import our module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from amazon_q_integration import AmazonQReviewer
except ImportError as e:
    print(f"❌ Failed to import Amazon Q integration module: {e}")
    print("Make sure amazon_q_integration.py is in the current directory")
    sys.exit(1)


def create_test_repository():
    """Create a temporary test repository with sample code files."""
    test_dir = tempfile.mkdtemp(prefix="amazonq_test_")
    test_path = Path(test_dir)
    
    # Create sample Python file with various patterns
    python_file = test_path / "sample.py"
    python_file.write_text('''#!/usr/bin/env python3
"""
Sample Python file for testing Amazon Q integration.
This file contains various patterns that should be detected.
"""

import os
import sys

# This is a potential security issue (hardcoded password)
DATABASE_PASSWORD = "hardcoded_password_123"

class SampleClass:
    """A sample class to test code quality analysis."""
    
    def __init__(self):
        self.data = []
    
    def long_function_example(self):
        """This function is intentionally long to test quality analysis."""
        # This function has many lines to trigger quality warnings
        result = []
        for i in range(100):
            if i % 2 == 0:
                result.append(i * 2)
            elif i % 3 == 0:
                result.append(i * 3)
            elif i % 5 == 0:
                result.append(i * 5)
            else:
                result.append(i)
        
        # More lines to make it longer
        processed = []
        for item in result:
            if item > 50:
                processed.append(item + 10)
            elif item > 25:
                processed.append(item + 5)
            else:
                processed.append(item + 1)
        
        return processed
    
    def potential_sql_injection(self, user_input):
        """Example of potential SQL injection vulnerability."""
        # This should be detected as a security issue
        query = f"SELECT * FROM users WHERE name = '{user_input}'"
        return query

def main():
    """Main function."""
    sample = SampleClass()
    result = sample.long_function_example()
    print(f"Result length: {len(result)}")

if __name__ == "__main__":
    main()
''')
    
    # Create sample JavaScript file
    js_file = test_path / "sample.js"
    js_file.write_text('''/**
 * Sample JavaScript file for testing Amazon Q integration.
 */

// Potential XSS vulnerability
function updateContent(userInput) {
    document.getElementById('content').innerHTML = userInput;
}

// Hardcoded API key (security issue)
const API_KEY = "sk-1234567890abcdef";

// Long function example
function processData(data) {
    let result = [];
    for (let i = 0; i < data.length; i++) {
        if (data[i].type === 'user') {
            result.push({
                id: data[i].id,
                name: data[i].name,
                email: data[i].email,
                processed: true
            });
        } else if (data[i].type === 'admin') {
            result.push({
                id: data[i].id,
                name: data[i].name,
                email: data[i].email,
                role: 'administrator',
                processed: true
            });
        }
    }
    return result;
}
''')
    
    # Create README file
    readme_file = test_path / "README.md"
    readme_file.write_text('''# Test Repository

This is a test repository for Amazon Q integration testing.

## Features

- Sample Python code
- Sample JavaScript code
- Various security and quality patterns for testing
''')
    
    # Create requirements.txt
    requirements_file = test_path / "requirements.txt"
    requirements_file.write_text('''flask>=2.0.0
requests>=2.25.0
boto3>=1.20.0
''')
    
    return str(test_path)


def test_aws_connectivity(reviewer):
    """Test AWS connectivity and service availability."""
    print("🔍 Testing AWS connectivity...")
    
    try:
        is_available = reviewer.is_available()
        if is_available:
            print("✅ AWS services are available and configured")
            return True
        else:
            print("⚠️  AWS services not available (will use mock mode)")
            return False
    except Exception as e:
        print(f"❌ Error testing AWS connectivity: {e}")
        return False


def test_mock_review(reviewer, test_repo_path):
    """Test the mock review functionality."""
    print("🔍 Testing mock review functionality...")
    
    try:
        results = reviewer.mock_review(test_repo_path)
        
        # Validate results structure
        required_keys = ['timestamp', 'repository_path', 'service_used', 'overall_score', 'mock_mode']
        for key in required_keys:
            if key not in results:
                print(f"❌ Missing required key in results: {key}")
                return False
        
        if not results.get('mock_mode'):
            print("❌ Mock mode not indicated in results")
            return False
        
        print(f"✅ Mock review completed successfully")
        print(f"   Overall Score: {results.get('overall_score', 'N/A')}/100")
        print(f"   Files Analyzed: {results.get('security_analysis', {}).get('total_files_scanned', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Mock review failed: {e}")
        return False


def test_full_review(reviewer, test_repo_path):
    """Test the full review functionality (with AWS services)."""
    print("🔍 Testing full review functionality...")
    
    try:
        results = reviewer.review_repository(test_repo_path)
        
        # Validate results structure
        required_keys = ['timestamp', 'repository_path', 'service_used', 'overall_score']
        for key in required_keys:
            if key not in results:
                print(f"❌ Missing required key in results: {key}")
                return False
        
        service_used = results.get('service_used', '')
        if 'mock' in service_used.lower():
            print("⚠️  Full review fell back to mock mode")
        else:
            print("✅ Full review completed with AWS services")
        
        print(f"   Overall Score: {results.get('overall_score', 'N/A')}/100")
        print(f"   Service Used: {service_used}")
        
        return True
        
    except Exception as e:
        print(f"❌ Full review failed: {e}")
        return False


def test_report_generation(reviewer, results):
    """Test report generation functionality."""
    print("🔍 Testing report generation...")
    
    try:
        report = reviewer.generate_report(results)
        
        if not report or len(report) < 100:
            print("❌ Generated report is too short or empty")
            return False
        
        if "Amazon Q Code Review Report" not in report:
            print("❌ Report doesn't contain expected header")
            return False
        
        print("✅ Report generation successful")
        print(f"   Report length: {len(report)} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return False


def test_configuration_loading():
    """Test configuration file loading."""
    print("🔍 Testing configuration loading...")
    
    config_file = Path("amazon_q_config.yaml")
    if not config_file.exists():
        print("⚠️  Configuration file not found (amazon_q_config.yaml)")
        return False
    
    try:
        import yaml
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check for required sections
        required_sections = ['aws', 'review', 'security', 'quality']
        for section in required_sections:
            if section not in config:
                print(f"⚠️  Missing configuration section: {section}")
        
        print("✅ Configuration file loaded successfully")
        return True
        
    except ImportError:
        print("⚠️  PyYAML not installed, skipping configuration test")
        return True
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test Amazon Q integration")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--mock-only", action="store_true", help="Only test mock mode")
    args = parser.parse_args()
    
    print("🚀 Amazon Q Integration Test Suite")
    print("=" * 50)
    
    # Test configuration loading
    config_ok = test_configuration_loading()
    
    # Create test repository
    print("📁 Creating test repository...")
    test_repo_path = create_test_repository()
    print(f"   Test repository created at: {test_repo_path}")
    
    # Initialize reviewer
    print("🔧 Initializing Amazon Q reviewer...")
    try:
        reviewer = AmazonQReviewer()
        print("✅ Amazon Q reviewer initialized")
    except Exception as e:
        print(f"❌ Failed to initialize reviewer: {e}")
        return 1
    
    # Test AWS connectivity (unless mock-only)
    aws_available = False
    if not args.mock_only:
        aws_available = test_aws_connectivity(reviewer)
    
    # Test mock review
    mock_ok = test_mock_review(reviewer, test_repo_path)
    
    # Test full review (if AWS available and not mock-only)
    full_ok = True
    if aws_available and not args.mock_only:
        full_ok = test_full_review(reviewer, test_repo_path)
    
    # Test report generation
    print("🔍 Getting results for report testing...")
    try:
        test_results = reviewer.mock_review(test_repo_path)
        report_ok = test_report_generation(reviewer, test_results)
    except Exception as e:
        print(f"❌ Failed to get results for report testing: {e}")
        report_ok = False
    
    # Cleanup
    print("🧹 Cleaning up test repository...")
    import shutil
    try:
        shutil.rmtree(test_repo_path)
        print("✅ Test repository cleaned up")
    except Exception as e:
        print(f"⚠️  Failed to cleanup test repository: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    tests = [
        ("Configuration Loading", config_ok),
        ("Mock Review", mock_ok),
        ("Report Generation", report_ok),
    ]
    
    if not args.mock_only:
        tests.append(("AWS Connectivity", aws_available))
        if aws_available:
            tests.append(("Full Review", full_ok))
    
    passed = 0
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Amazon Q integration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())