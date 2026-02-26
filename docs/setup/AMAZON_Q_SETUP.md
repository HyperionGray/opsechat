# Amazon Q Integration Configuration

## AWS Credentials Setup

To enable Amazon Q Developer CLI integration, you need to configure AWS credentials. Choose one of the following methods:

### Method 1: Environment Variables (Recommended for Development)

```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Method 2: AWS Credentials File

Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key

[amazon-q]
aws_access_key_id = your-q-specific-key
aws_secret_access_key = your-q-specific-secret
```

Create `~/.aws/config`:
```ini
[default]
region = us-east-1
output = json

[profile amazon-q]
region = us-east-1
output = json
```

### Method 3: GitHub Repository Secrets (For CI/CD)

Add the following secrets to your GitHub repository:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Amazon Q Developer CLI Installation

### Prerequisites

1. **AWS CLI v2** (required)
   ```bash
   # Install AWS CLI v2
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   ```

2. **Python 3.8+** (already required by opsechat)

### Installation Steps

**Note**: Amazon Q Developer CLI is not yet publicly available. This configuration is prepared for future release.

When available, installation will likely follow this pattern:

```bash
# Install Amazon Q CLI (when available)
pip install amazon-q-developer-cli

# Or via AWS CLI extension
aws configure add-model --service-model file://amazon-q-service-model.json
```

## Configuration for opsechat

### 1. Enable AWS Integration in opsechat

Add to your environment or `.env` file:
```bash
# Enable AWS integration (optional)
ENABLE_AWS_INTEGRATION=true

# Amazon Q configuration
AMAZON_Q_ENABLED=true
AMAZON_Q_PROFILE=amazon-q
AMAZON_Q_REGION=us-east-1

# CodeWhisperer configuration
CODEWHISPERER_ENABLED=true
```

### 2. Custom Review Rules

Create `amazon-q-rules.json` in your project root:
```json
{
  "rules": {
    "security": {
      "scan_for_secrets": true,
      "check_dependencies": true,
      "validate_input_sanitization": true,
      "check_authentication": true
    },
    "performance": {
      "analyze_algorithms": true,
      "check_memory_usage": true,
      "identify_bottlenecks": true
    },
    "architecture": {
      "validate_patterns": true,
      "check_separation_of_concerns": true,
      "analyze_coupling": true
    },
    "custom_rules": [
      {
        "name": "tor_security_check",
        "description": "Validate Tor integration security",
        "pattern": "Controller\\.|stem\\.",
        "severity": "medium"
      },
      {
        "name": "session_security",
        "description": "Check session handling security",
        "pattern": "session\\[|app\\.secret_key",
        "severity": "high"
      }
    ]
  },
  "exclusions": {
    "files": [
      "tests/*",
      "*.md",
      ".github/*"
    ],
    "patterns": [
      "# Test data",
      "# Example"
    ]
  }
}
```

## Integration with opsechat Security Model

### Privacy Considerations

Amazon Q integration is designed to work alongside opsechat's privacy-focused architecture:

1. **Local Analysis**: Code analysis happens locally when possible
2. **Minimal Data Sharing**: Only necessary code patterns are analyzed
3. **Ephemeral Sessions**: No persistent data stored in AWS
4. **Tor Compatibility**: AWS integration doesn't interfere with Tor functionality

### Security Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                    opsechat Application                     │
├─────────────────────────────────────────────────────────────┤
│  Tor Hidden Service  │  Chat/Email System  │  AWS Optional  │
│  (Always Active)     │  (Core Features)    │  (Enhancement) │
├─────────────────────────────────────────────────────────────┤
│                    Security Layers                          │
│  • Input Sanitization    • Session Isolation               │
│  • Memory-only Storage   • Ephemeral Services              │
│  • Amazon Q Analysis    • Dependency Scanning              │
└─────────────────────────────────────────────────────────────┘
```

## Verification

### Test AWS Configuration

```bash
# Test AWS credentials
aws sts get-caller-identity

# Test Amazon Q access (when available)
amazon-q --version
amazon-q scan --help
```

### Test Integration with opsechat

```bash
# Run with AWS integration enabled
ENABLE_AWS_INTEGRATION=true python runserver.py

# Check logs for AWS integration status
grep -i "aws\|amazon" logs/opsechat.log
```

## Troubleshooting

### Common Issues

1. **AWS Credentials Not Found**
   ```
   Error: Unable to locate credentials
   Solution: Verify AWS credentials configuration
   ```

2. **Amazon Q CLI Not Available**
   ```
   Error: amazon-q command not found
   Solution: Wait for public release or use alternative scanning
   ```

3. **Permission Denied**
   ```
   Error: Access denied for Amazon Q
   Solution: Verify IAM permissions for CodeWhisperer and Q services
   ```

### Required IAM Permissions

When Amazon Q becomes available, you'll need these permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "codewhisperer:*",
        "amazonq:*",
        "codeguru:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Support

For issues with:
- **AWS Configuration**: Check AWS documentation
- **Amazon Q Integration**: Monitor AWS announcements for public release
- **opsechat Compatibility**: Open an issue in this repository

---

**Note**: This configuration is prepared for Amazon Q Developer CLI when it becomes publicly available. Current functionality uses alternative security scanning tools as placeholders.