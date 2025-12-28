# Amazon Q Developer CLI Integration Guide

## Overview

This guide provides instructions for integrating Amazon Q Developer CLI with the OpSecChat project to enable automated code reviews, security scanning, and performance optimization recommendations.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Amazon Q Developer CLI (when available)
- GitHub repository with Actions enabled

## Amazon Q Developer CLI Setup

### Installation

```bash
# Install Amazon Q Developer CLI (when available)
# This is a placeholder for the official installation method
curl -sSL https://amazon-q-cli.amazonaws.com/install.sh | bash

# Alternative: Install via npm (hypothetical)
npm install -g @aws/amazon-q-cli

# Alternative: Install via pip (hypothetical)
pip install amazon-q-developer-cli
```

### Configuration

```bash
# Configure Amazon Q CLI with AWS credentials
amazon-q configure

# Set up project-specific configuration
amazon-q init --project-type python-flask --security-focus
```

## Custom Review Rules Configuration

### Security Rules for OpSecChat

Create `.amazon-q/security-rules.json`:

```json
{
  "version": "1.0",
  "rules": [
    {
      "id": "tor-security-check",
      "name": "Tor Hidden Service Security",
      "description": "Validate Tor hidden service implementation",
      "severity": "medium",
      "patterns": [
        {
          "pattern": "Controller\\.from_port\\(",
          "message": "Ensure Tor controller connection is properly secured",
          "suggestion": "Verify authentication and error handling for Tor connections"
        },
        {
          "pattern": "create_ephemeral_hidden_service\\(",
          "message": "Validate ephemeral hidden service configuration",
          "suggestion": "Ensure proper cleanup and error handling for hidden services"
        }
      ]
    },
    {
      "id": "pgp-message-handling",
      "name": "PGP Message Preservation",
      "description": "Ensure PGP messages are not sanitized",
      "severity": "high",
      "patterns": [
        {
          "pattern": "-----BEGIN PGP MESSAGE-----",
          "context": "sanitization",
          "message": "PGP messages must not be sanitized",
          "suggestion": "Add conditional check to skip sanitization for PGP content"
        }
      ]
    },
    {
      "id": "session-security",
      "name": "Session Key Generation",
      "description": "Validate secure session key generation",
      "severity": "medium",
      "patterns": [
        {
          "pattern": "app\\.secret_key\\s*=",
          "message": "Ensure session key is cryptographically secure",
          "suggestion": "Use secrets module for production deployments"
        }
      ]
    },
    {
      "id": "input-validation",
      "name": "Input Validation",
      "description": "Ensure all user inputs are properly validated",
      "severity": "high",
      "patterns": [
        {
          "pattern": "request\\.form\\[",
          "message": "Validate and sanitize form input",
          "suggestion": "Apply appropriate validation and sanitization"
        },
        {
          "pattern": "request\\.args\\[",
          "message": "Validate and sanitize query parameters",
          "suggestion": "Apply appropriate validation and sanitization"
        }
      ]
    },
    {
      "id": "memory-cleanup",
      "name": "Memory Management",
      "description": "Ensure proper cleanup of sensitive data",
      "severity": "medium",
      "patterns": [
        {
          "pattern": "chatlines\\.pop\\(",
          "message": "Verify index deletion is performed correctly",
          "suggestion": "Use reversed() iteration when deleting by index"
        }
      ]
    }
  ]
}
```

### Performance Rules

Create `.amazon-q/performance-rules.json`:

```json
{
  "version": "1.0",
  "rules": [
    {
      "id": "algorithm-efficiency",
      "name": "Algorithm Efficiency",
      "description": "Check for inefficient algorithms",
      "severity": "low",
      "patterns": [
        {
          "pattern": "for.*in.*range\\(len\\(",
          "message": "Consider using enumerate() or direct iteration",
          "suggestion": "Use enumerate() for index-value pairs or iterate directly"
        }
      ]
    },
    {
      "id": "caching-opportunities",
      "name": "Caching Opportunities",
      "description": "Identify repeated computations that could be cached",
      "severity": "low",
      "patterns": [
        {
          "pattern": "get_review_stats\\(\\)",
          "message": "Consider caching review statistics",
          "suggestion": "Implement caching with invalidation on data changes"
        }
      ]
    },
    {
      "id": "resource-management",
      "name": "Resource Management",
      "description": "Ensure proper resource cleanup",
      "severity": "medium",
      "patterns": [
        {
          "pattern": "with\\s+.*:",
          "message": "Good use of context manager for resource management",
          "type": "positive"
        }
      ]
    }
  ]
}
```

### Architecture Rules

Create `.amazon-q/architecture-rules.json`:

```json
{
  "version": "1.0",
  "rules": [
    {
      "id": "separation-of-concerns",
      "name": "Separation of Concerns",
      "description": "Validate module boundaries and responsibilities",
      "severity": "medium",
      "patterns": [
        {
          "pattern": "from\\s+runserver\\s+import",
          "message": "Avoid importing from main application module",
          "suggestion": "Extract shared functionality to separate modules"
        }
      ]
    },
    {
      "id": "dependency-management",
      "name": "Dependency Management",
      "description": "Check for circular dependencies and coupling",
      "severity": "medium",
      "patterns": [
        {
          "pattern": "import.*email_system.*import.*runserver",
          "message": "Potential circular dependency detected",
          "suggestion": "Refactor to remove circular dependencies"
        }
      ]
    },
    {
      "id": "error-handling",
      "name": "Error Handling",
      "description": "Ensure proper error handling patterns",
      "severity": "medium",
      "patterns": [
        {
          "pattern": "try:",
          "context": "no_except",
          "message": "Try block without except clause",
          "suggestion": "Add appropriate exception handling"
        }
      ]
    }
  ]
}
```

## GitHub Actions Integration

The Amazon Q integration is already configured in `.github/workflows/amazon-q-review.yml`. Key features:

### Automated Security Scanning
- Runs on every push and pull request
- Weekly scheduled scans
- Multiple security tools integration (Bandit, Safety, Semgrep, CodeQL)

### Custom Rule Application
- Applies OpSecChat-specific security rules
- Validates Tor and PGP handling
- Checks session security implementation

### Report Generation
- Creates comprehensive security reports
- Uploads artifacts for review
- Comments on pull requests with summaries

## Manual Amazon Q CLI Usage

### Running Security Scans

```bash
# Run comprehensive security scan
amazon-q scan --type security --config .amazon-q/security-rules.json

# Run performance analysis
amazon-q scan --type performance --config .amazon-q/performance-rules.json

# Run architecture review
amazon-q scan --type architecture --config .amazon-q/architecture-rules.json

# Run all scans
amazon-q scan --all --output-format json > amazon-q-report.json
```

### Code Review Integration

```bash
# Review specific files
amazon-q review runserver.py email_system.py

# Review changes in pull request
amazon-q review --pr-number 123

# Generate improvement suggestions
amazon-q suggest --file runserver.py --focus security
```

### Performance Analysis

```bash
# Analyze performance bottlenecks
amazon-q performance --profile

# Check memory usage patterns
amazon-q memory-analysis

# Identify caching opportunities
amazon-q cache-analysis
```

## Configuration Files

### Main Configuration

Create `.amazon-q/config.yaml`:

```yaml
version: "1.0"
project:
  name: "opsechat"
  type: "python-flask"
  description: "Secure anonymous chat and email system"

scanning:
  security:
    enabled: true
    rules: ".amazon-q/security-rules.json"
    severity_threshold: "medium"
  
  performance:
    enabled: true
    rules: ".amazon-q/performance-rules.json"
    threshold_ms: 100
  
  architecture:
    enabled: true
    rules: ".amazon-q/architecture-rules.json"
    complexity_threshold: 10

reporting:
  format: "markdown"
  output_dir: ".amazon-q/reports"
  include_suggestions: true
  include_code_examples: true

integration:
  github:
    enabled: true
    comment_on_pr: true
    create_issues: false
  
  aws:
    region: "us-east-1"
    s3_bucket: "opsechat-amazon-q-reports"

exclusions:
  paths:
    - "tests/"
    - "bak/"
    - "node_modules/"
  
  files:
    - "*.pyc"
    - "*.log"
    - ".git/*"
```

### Environment-Specific Configuration

Create `.amazon-q/environments/production.yaml`:

```yaml
extends: "../config.yaml"

scanning:
  security:
    severity_threshold: "low"  # More strict for production
  
  performance:
    threshold_ms: 50  # Stricter performance requirements

reporting:
  include_sensitive_data: false
  anonymize_paths: true

integration:
  aws:
    s3_bucket: "opsechat-amazon-q-reports-prod"
```

## CodeWhisperer Integration

### Setup

```bash
# Enable CodeWhisperer for the project
amazon-q codewhisperer enable

# Configure for Python/Flask
amazon-q codewhisperer configure --language python --framework flask
```

### Custom Suggestions

Create `.amazon-q/codewhisperer-config.json`:

```json
{
  "suggestions": {
    "security": {
      "enabled": true,
      "focus_areas": [
        "input_validation",
        "session_management",
        "cryptography",
        "tor_integration"
      ]
    },
    "performance": {
      "enabled": true,
      "focus_areas": [
        "memory_management",
        "algorithm_optimization",
        "caching"
      ]
    },
    "best_practices": {
      "enabled": true,
      "frameworks": ["flask", "tor", "pgp"]
    }
  },
  "exclusions": {
    "patterns": [
      "test_*",
      "*_test.py",
      "bak/*"
    ]
  }
}
```

## Monitoring and Alerts

### CloudWatch Integration

```bash
# Set up CloudWatch metrics for Amazon Q scans
amazon-q cloudwatch setup --metric-namespace "OpSecChat/AmazonQ"

# Create alarms for security findings
aws cloudwatch put-metric-alarm \
  --alarm-name "OpSecChat-HighSeverityFindings" \
  --alarm-description "Alert on high severity security findings" \
  --metric-name "SecurityFindings" \
  --namespace "OpSecChat/AmazonQ" \
  --statistic "Sum" \
  --period 3600 \
  --threshold 1 \
  --comparison-operator "GreaterThanOrEqualToThreshold"
```

### Notification Setup

```bash
# Set up SNS topic for notifications
aws sns create-topic --name opsechat-amazon-q-alerts

# Subscribe to notifications
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT:opsechat-amazon-q-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

## Best Practices

### Security Review Workflow

1. **Pre-commit Hooks**: Run Amazon Q scans before commits
2. **Pull Request Reviews**: Automated scanning on PR creation
3. **Scheduled Scans**: Weekly comprehensive reviews
4. **Dependency Monitoring**: Daily checks for new vulnerabilities

### Performance Monitoring

1. **Baseline Establishment**: Regular performance benchmarking
2. **Regression Detection**: Alert on performance degradation
3. **Optimization Tracking**: Monitor improvement implementations

### Architecture Evolution

1. **Design Review**: Validate architectural changes
2. **Complexity Monitoring**: Track code complexity metrics
3. **Dependency Analysis**: Monitor coupling and cohesion

## Troubleshooting

### Common Issues

#### 1. Authentication Problems
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Reconfigure Amazon Q
amazon-q configure --reset
```

#### 2. Rule Configuration Errors
```bash
# Validate rule syntax
amazon-q validate-rules .amazon-q/security-rules.json

# Test rule patterns
amazon-q test-pattern "Controller\.from_port\(" runserver.py
```

#### 3. Integration Issues
```bash
# Check GitHub integration
amazon-q github status

# Verify webhook configuration
amazon-q github webhook verify
```

### Debug Mode

```bash
# Enable debug logging
export AMAZON_Q_DEBUG=true

# Run with verbose output
amazon-q scan --verbose --debug
```

## Future Enhancements

### Planned Features

1. **AI-Powered Suggestions**: Enhanced code improvement recommendations
2. **Custom Model Training**: Train on OpSecChat-specific patterns
3. **Integration Expansion**: Support for more CI/CD platforms
4. **Real-time Analysis**: Live code analysis during development

### Experimental Features

```bash
# Enable experimental features
amazon-q experimental enable --feature ai-suggestions

# Try beta integrations
amazon-q beta --integration vscode
```

## Support and Resources

- **Amazon Q Developer Documentation**: https://docs.aws.amazon.com/amazonq/
- **AWS CodeWhisperer**: https://aws.amazon.com/codewhisperer/
- **GitHub Actions Integration**: https://github.com/aws-actions/
- **OpSecChat Security Guidelines**: See SECURITY.md

For issues with Amazon Q integration, check the AWS service health dashboard and review CloudWatch logs for detailed error information.