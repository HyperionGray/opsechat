"""
AWS Integration Module for opsechat

This module provides optional AWS integration for Amazon Q Developer CLI
and CodeWhisperer security scanning without compromising the core
privacy-focused architecture of opsechat.

Features:
- Optional AWS SDK integration
- Amazon Q Developer CLI support (when available)
- CodeWhisperer security scanning
- Maintains privacy and security boundaries
"""

import os
import logging
from typing import Dict, Optional, Any
import json
import time

# Optional AWS imports - gracefully handle if not available
try:
    import boto3
    import botocore
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

logger = logging.getLogger(__name__)


class AWSIntegration:
    """
    AWS Integration manager for opsechat
    
    Provides optional AWS services integration while maintaining
    the privacy-focused design of the application.
    """
    
    def __init__(self):
        self.enabled = self._check_enabled()
        self.profile = os.environ.get('AMAZON_Q_PROFILE', 'default')
        self.region = os.environ.get('AMAZON_Q_REGION', 'us-east-1')
        self._session = None
        self._codewhisperer_enabled = os.environ.get('CODEWHISPERER_ENABLED', 'false').lower() == 'true'
        
        if self.enabled and AWS_AVAILABLE:
            self._initialize_session()
    
    def _check_enabled(self) -> bool:
        """Check if AWS integration is enabled via environment variables"""
        return os.environ.get('ENABLE_AWS_INTEGRATION', 'false').lower() == 'true'
    
    def _initialize_session(self) -> None:
        """Initialize AWS session with configured profile"""
        try:
            if self.profile != 'default':
                self._session = boto3.Session(profile_name=self.profile, region_name=self.region)
            else:
                self._session = boto3.Session(region_name=self.region)
            
            # Test credentials
            sts = self._session.client('sts')
            identity = sts.get_caller_identity()
            logger.info(f"AWS integration initialized for account: {identity.get('Account', 'unknown')}")
            
        except Exception as e:
            logger.warning(f"Failed to initialize AWS session: {e}")
            self.enabled = False
            self._session = None
    
    def is_available(self) -> bool:
        """Check if AWS integration is available and properly configured"""
        return self.enabled and AWS_AVAILABLE and self._session is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Get AWS integration status"""
        status = {
            'aws_sdk_available': AWS_AVAILABLE,
            'integration_enabled': self.enabled,
            'session_initialized': self._session is not None,
            'profile': self.profile,
            'region': self.region,
            'codewhisperer_enabled': self._codewhisperer_enabled
        }
        
        if self._session:
            try:
                sts = self._session.client('sts')
                identity = sts.get_caller_identity()
                status['account_id'] = identity.get('Account')
                status['user_arn'] = identity.get('Arn')
            except Exception as e:
                status['error'] = str(e)
        
        return status
    
    def scan_code_security(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Perform security scan using AWS CodeWhisperer (when available)
        
        Note: This is a placeholder for when Amazon Q Developer CLI becomes available
        """
        if not self.is_available() or not self._codewhisperer_enabled:
            return None
        
        # Placeholder for future CodeWhisperer integration
        logger.info(f"CodeWhisperer scan requested for: {file_path}")
        
        # For now, return a placeholder response
        return {
            'status': 'placeholder',
            'message': 'Amazon Q Developer CLI not yet available',
            'file': file_path,
            'timestamp': time.time()
        }
    
    def analyze_dependencies(self, requirements_file: str = 'requirements.txt') -> Optional[Dict[str, Any]]:
        """
        Analyze dependencies for security vulnerabilities using AWS services
        """
        if not self.is_available():
            return None
        
        if not os.path.exists(requirements_file):
            return {'error': f'Requirements file not found: {requirements_file}'}
        
        # Read requirements
        with open(requirements_file, 'r') as f:
            requirements = f.read()
        
        # Placeholder for AWS-based dependency analysis
        logger.info(f"Dependency analysis requested for: {requirements_file}")
        
        return {
            'status': 'analyzed',
            'file': requirements_file,
            'dependencies_count': len([line for line in requirements.split('\n') if line.strip() and not line.startswith('#')]),
            'timestamp': time.time(),
            'note': 'AWS-based analysis placeholder - use local tools for now'
        }
    
    def generate_security_report(self, project_path: str = '.') -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive security report using AWS services
        """
        if not self.is_available():
            return None
        
        report = {
            'project_path': project_path,
            'timestamp': time.time(),
            'aws_integration': self.get_status(),
            'scans': []
        }
        
        # Scan Python files
        for root, dirs, files in os.walk(project_path):
            # Skip hidden directories and common excludes
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    scan_result = self.scan_code_security(file_path)
                    if scan_result:
                        report['scans'].append(scan_result)
        
        # Analyze dependencies
        deps_analysis = self.analyze_dependencies()
        if deps_analysis:
            report['dependency_analysis'] = deps_analysis
        
        return report


class SecurityScanner:
    """
    Local security scanner that works with or without AWS integration
    """
    
    def __init__(self, aws_integration: Optional[AWSIntegration] = None):
        self.aws = aws_integration
    
    def scan_for_secrets(self, file_path: str) -> Dict[str, Any]:
        """Scan file for potential hardcoded secrets"""
        secrets_patterns = [
            r'password\s*=\s*[\'"][^\'"]+[\'"]',
            r'api_key\s*=\s*[\'"][^\'"]+[\'"]',
            r'secret\s*=\s*[\'"][^\'"]+[\'"]',
            r'token\s*=\s*[\'"][^\'"]+[\'"]',
        ]
        
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    # Skip comments and test files
                    if line.strip().startswith('#') or 'test' in file_path.lower():
                        continue
                    
                    for pattern in secrets_patterns:
                        import re
                        if re.search(pattern, line, re.IGNORECASE):
                            # Check for common false positives
                            if any(fp in line.lower() for fp in ['placeholder', 'example', 'test', '""', "''"]):
                                continue
                            
                            findings.append({
                                'line': i,
                                'content': line.strip(),
                                'pattern': pattern,
                                'severity': 'high'
                            })
        
        except Exception as e:
            return {'error': str(e)}
        
        return {
            'file': file_path,
            'findings': findings,
            'status': 'clean' if not findings else 'issues_found'
        }
    
    def validate_tor_integration(self, file_path: str) -> Dict[str, Any]:
        """Validate Tor integration security practices"""
        tor_checks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for proper error handling
                if 'Controller.from_port' in content:
                    if 'try:' in content and 'except' in content:
                        tor_checks.append({'check': 'error_handling', 'status': 'pass'})
                    else:
                        tor_checks.append({'check': 'error_handling', 'status': 'fail', 'message': 'Missing error handling for Tor connection'})
                
                # Check for service cleanup
                if 'create_ephemeral_hidden_service' in content:
                    if 'remove_ephemeral_hidden_service' in content:
                        tor_checks.append({'check': 'service_cleanup', 'status': 'pass'})
                    else:
                        tor_checks.append({'check': 'service_cleanup', 'status': 'warning', 'message': 'Ensure ephemeral service cleanup'})
        
        except Exception as e:
            return {'error': str(e)}
        
        return {
            'file': file_path,
            'checks': tor_checks,
            'status': 'validated'
        }


# Global instance
aws_integration = AWSIntegration()
security_scanner = SecurityScanner(aws_integration)


def get_aws_status() -> Dict[str, Any]:
    """Get current AWS integration status"""
    return aws_integration.get_status()


def is_aws_enabled() -> bool:
    """Check if AWS integration is enabled and available"""
    return aws_integration.is_available()


def scan_project_security(project_path: str = '.') -> Dict[str, Any]:
    """
    Perform comprehensive security scan of the project
    Uses AWS services if available, falls back to local scanning
    """
    report = {
        'timestamp': time.time(),
        'project_path': project_path,
        'aws_integration': get_aws_status(),
        'local_scans': [],
        'aws_scans': None
    }
    
    # Local security scanning
    for root, dirs, files in os.walk(project_path):
        # Skip hidden directories and common excludes
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'bak']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                
                # Scan for secrets
                secrets_scan = security_scanner.scan_for_secrets(file_path)
                if secrets_scan.get('findings'):
                    report['local_scans'].append(secrets_scan)
                
                # Validate Tor integration
                if 'runserver.py' in file:
                    tor_scan = security_scanner.validate_tor_integration(file_path)
                    report['local_scans'].append(tor_scan)
    
    # AWS-based scanning if available
    if is_aws_enabled():
        aws_report = aws_integration.generate_security_report(project_path)
        report['aws_scans'] = aws_report
    
    return report


if __name__ == '__main__':
    # Test AWS integration
    print("AWS Integration Status:")
    print(json.dumps(get_aws_status(), indent=2))
    
    print("\nRunning security scan...")
    scan_result = scan_project_security()
    print(json.dumps(scan_result, indent=2))