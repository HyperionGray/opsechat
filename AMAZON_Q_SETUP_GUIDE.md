# Amazon Q Code Review Integration Setup Guide

This guide provides comprehensive instructions for setting up Amazon Q Code Review integration in your repository.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [AWS Account Setup](#aws-account-setup)
3. [IAM Permissions Configuration](#iam-permissions-configuration)
4. [Repository Secrets Configuration](#repository-secrets-configuration)
5. [Amazon Q Developer CLI Setup](#amazon-q-developer-cli-setup)
6. [CodeWhisperer Security Scanning](#codewhisperer-security-scanning)
7. [Custom Review Rules](#custom-review-rules)
8. [Testing the Integration](#testing-the-integration)
9. [Troubleshooting](#troubleshooting)
10. [Cost Management](#cost-management)

## Prerequisites

Before setting up Amazon Q integration, ensure you have:

- An AWS account with appropriate permissions
- Repository admin access to configure secrets
- Basic understanding of AWS IAM and services
- Python 3.8+ (for local testing)

## AWS Account Setup

### 1. Create AWS Account

If you don't have an AWS account:
1. Go to [AWS Console](https://aws.amazon.com/)
2. Click "Create an AWS Account"
3. Follow the registration process
4. Verify your account with a credit card

### 2. Enable Required Services

Enable the following AWS services in your account:
- **Amazon CodeWhisperer** (for security scanning)
- **Amazon Bedrock** (for AI-powered analysis)
- **AWS Identity and Access Management (IAM)**

## IAM Permissions Configuration

### 1. Create IAM User for GitHub Actions

Create a dedicated IAM user for the GitHub Actions integration:

```bash
# Using AWS CLI
aws iam create-user --user-name github-amazonq-integration
```

### 2. Create IAM Policy

Create a custom policy with the minimum required permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "codewhisperer:GenerateRecommendations",
                "codewhisperer:GetRecommendations",
                "codewhisperer:ListRecommendations"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

Save this as `amazon-q-policy.json` and create the policy:

```bash
aws iam create-policy \
    --policy-name AmazonQCodeReviewPolicy \
    --policy-document file://amazon-q-policy.json
```

### 3. Attach Policy to User

```bash
aws iam attach-user-policy \
    --user-name github-amazonq-integration \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/AmazonQCodeReviewPolicy
```

### 4. Create Access Keys

```bash
aws iam create-access-key --user-name github-amazonq-integration
```

**Important**: Save the Access Key ID and Secret Access Key securely. You'll need them for GitHub secrets.

## Repository Secrets Configuration

### 1. Add AWS Credentials to GitHub Secrets

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `AWS_ACCESS_KEY_ID` | Your access key ID | AWS access key for authentication |
| `AWS_SECRET_ACCESS_KEY` | Your secret access key | AWS secret key for authentication |
| `AWS_DEFAULT_REGION` | `us-east-1` (or your preferred region) | AWS region for services |

### 2. Optional: Add Custom Configuration

You can also add custom configuration as a secret:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `AMAZON_Q_CONFIG` | YAML configuration content | Custom review rules and settings |

## Amazon Q Developer CLI Setup

### 1. Install Amazon Q Developer CLI

When Amazon Q Developer CLI becomes available, install it:

```bash
# This will be available in the future
npm install -g @aws/amazon-q-developer-cli
# or
pip install amazon-q-developer-cli
```

### 2. Configure CLI

```bash
# Configure with your AWS credentials
amazon-q configure --access-key-id YOUR_ACCESS_KEY_ID \
                   --secret-access-key YOUR_SECRET_ACCESS_KEY \
                   --region us-east-1
```

**Note**: Currently, Amazon Q Developer CLI is not publicly available. The integration uses AWS SDK with CodeWhisperer and Bedrock services.

## CodeWhisperer Security Scanning

### 1. Enable CodeWhisperer

1. Go to [AWS CodeWhisperer Console](https://console.aws.amazon.com/codewhisperer/)
2. Enable CodeWhisperer for your account
3. Configure security scanning settings

### 2. Set Up Security Scanning

CodeWhisperer security scanning is automatically enabled when you have the proper IAM permissions. The integration will:

- Scan source code files for security vulnerabilities
- Detect hardcoded secrets and credentials
- Identify potential injection vulnerabilities
- Check for insecure coding patterns

## Custom Review Rules

### 1. Configuration File

The integration uses `amazon_q_config.yaml` for custom rules. Key sections:

```yaml
# Security configuration
security:
  custom_patterns:
    hardcoded_secrets:
      - "password\\s*=\\s*[\"'][^\"']+[\"']"
      - "api_key\\s*=\\s*[\"'][^\"']+[\"']"

# Quality thresholds
quality:
  thresholds:
    maintainability_score: 70
    complexity_score: 60
    documentation_score: 80
```

### 2. Customizing Rules

Edit `amazon_q_config.yaml` to:
- Add custom security patterns
- Adjust quality thresholds
- Configure architecture analysis
- Set reporting preferences

## Testing the Integration

### 1. Local Testing

Test the integration locally:

```bash
# Install dependencies
pip install boto3 botocore

# Set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1

# Run the integration
python amazon_q_integration.py .
```

### 2. GitHub Actions Testing

1. Push changes to trigger the workflow
2. Check the Actions tab for workflow execution
3. Review the generated Amazon Q review issue

### 3. Verify Integration Status

The integration will indicate its status:
- ✅ **Full Integration Active**: AWS services available
- ⚠️ **Mock Mode Active**: AWS credentials not configured
- ❌ **Integration Failed**: Configuration or connectivity issues

## Troubleshooting

### Common Issues

#### 1. AWS Credentials Not Found

**Error**: `NoCredentialsError: Unable to locate credentials`

**Solution**:
- Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set in repository secrets
- Check that the secrets have the correct names (case-sensitive)
- Ensure the IAM user has the required permissions

#### 2. Permission Denied

**Error**: `AccessDenied: User is not authorized to perform action`

**Solution**:
- Review IAM policy permissions
- Ensure the policy is attached to the correct user
- Check that the services (CodeWhisperer, Bedrock) are available in your region

#### 3. Service Not Available

**Error**: `ServiceUnavailable: The requested service is not available`

**Solution**:
- Check if CodeWhisperer is available in your AWS region
- Verify that Bedrock is enabled in your account
- Try a different AWS region (us-east-1 recommended)

#### 4. Rate Limiting

**Error**: `ThrottlingException: Rate exceeded`

**Solution**:
- Reduce the number of files analyzed (set `max_files` in config)
- Add delays between API calls
- Consider upgrading your AWS service limits

### Debug Mode

Enable verbose logging by setting in `amazon_q_config.yaml`:

```yaml
integration:
  verbose_logging: true
```

### Mock Mode Fallback

If AWS services are unavailable, the integration automatically falls back to mock mode:
- Provides local analysis using heuristics
- Generates comprehensive reports
- Maintains workflow functionality

## Cost Management

### 1. Understanding Costs

Amazon Q integration may incur costs for:
- CodeWhisperer API calls
- Bedrock model invocations
- Data transfer

### 2. Cost Control Measures

- Set `max_files` limit in configuration
- Use mock mode for development/testing
- Monitor AWS billing dashboard
- Set up billing alerts

### 3. Free Tier Usage

- CodeWhisperer Individual: Free tier available
- Bedrock: Pay-per-use pricing
- Check current AWS pricing for exact costs

## Advanced Configuration

### 1. Environment-Specific Settings

Configure different settings for different environments:

```yaml
environments:
  development:
    security:
      severity_threshold: "low"
  production:
    security:
      severity_threshold: "high"
```

### 2. Custom Integration

For advanced use cases, you can extend the `amazon_q_integration.py` module:

```python
from amazon_q_integration import AmazonQReviewer

# Create custom reviewer
reviewer = AmazonQReviewer(region='us-west-2')

# Add custom analysis
def custom_analysis(repo_path):
    # Your custom logic here
    pass

# Integrate with existing workflow
```

## Support and Resources

### Documentation
- [AWS CodeWhisperer Documentation](https://docs.aws.amazon.com/codewhisperer/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

### Community
- [AWS Developer Forums](https://forums.aws.amazon.com/)
- [GitHub Issues](https://github.com/your-repo/issues) for integration-specific problems

### Getting Help

If you encounter issues:
1. Check the troubleshooting section above
2. Review AWS CloudTrail logs for API call details
3. Enable debug logging for detailed error information
4. Create an issue in the repository with error details

---

## Quick Start Checklist

- [ ] AWS account created and verified
- [ ] IAM user created with proper permissions
- [ ] AWS credentials added to GitHub repository secrets
- [ ] CodeWhisperer enabled in AWS account
- [ ] Integration tested locally (optional)
- [ ] GitHub Actions workflow triggered and verified
- [ ] Amazon Q review issue created successfully

Once completed, your repository will have automated Amazon Q code reviews on every push and workflow completion!