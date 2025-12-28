# Repository Secrets Configuration Guide

This guide provides instructions for configuring the necessary repository secrets to enable Amazon Q Code Review integration and AWS deployment capabilities.

## Required Secrets

### AWS Credentials

#### AWS_ACCESS_KEY_ID
- **Purpose**: AWS access key for authentication
- **Required for**: CloudFormation deployment, ECS management, Secrets Manager access
- **Security Level**: High - Provides AWS API access

**How to obtain:**
1. Log into AWS Console
2. Navigate to IAM > Users
3. Select your user or create a new service user
4. Go to Security Credentials tab
5. Create Access Key
6. Copy the Access Key ID

#### AWS_SECRET_ACCESS_KEY
- **Purpose**: AWS secret key for authentication
- **Required for**: All AWS API operations
- **Security Level**: Critical - Must be kept secure

**How to obtain:**
1. When creating the Access Key (above)
2. Copy the Secret Access Key immediately
3. Store securely - it won't be shown again

### Optional Secrets

#### GITHUB_TOKEN
- **Purpose**: GitHub API access for enhanced integration
- **Required for**: Advanced GitHub Actions features, PR comments
- **Security Level**: Medium - Repository access only

**How to obtain:**
1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `workflow`, `write:packages`
4. Copy the generated token

#### DOCKER_HUB_USERNAME / DOCKER_HUB_TOKEN
- **Purpose**: Docker Hub authentication for image pushing
- **Required for**: If using Docker Hub instead of ECR
- **Security Level**: Medium - Container registry access

#### SLACK_WEBHOOK_URL
- **Purpose**: Slack notifications for deployment status
- **Required for**: Optional notification integration
- **Security Level**: Low - Webhook access only

## Setting Up Repository Secrets

### GitHub Repository Secrets

1. **Navigate to Repository Settings**
   - Go to your GitHub repository
   - Click on "Settings" tab
   - Select "Secrets and variables" > "Actions"

2. **Add New Repository Secret**
   - Click "New repository secret"
   - Enter secret name (e.g., `AWS_ACCESS_KEY_ID`)
   - Enter secret value
   - Click "Add secret"

3. **Required Secrets to Add**
   ```
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   ```

4. **Optional Secrets**
   ```
   GITHUB_TOKEN=ghp_...
   DOCKER_HUB_USERNAME=your-username
   DOCKER_HUB_TOKEN=...
   SLACK_WEBHOOK_URL=https://hooks.slack.com/...
   ```

### Environment Variables

For local development, create a `.env` file (never commit this):

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1

# Application Configuration
TOR_CONTROL_HOST=127.0.0.1
TOR_CONTROL_PORT=9051
FLASK_SECRET_KEY=your_random_secret_key_here
ENVIRONMENT=development

# Optional: Docker Hub
DOCKER_HUB_USERNAME=your_username
DOCKER_HUB_TOKEN=your_token

# Optional: GitHub
GITHUB_TOKEN=your_github_token
```

## AWS IAM Policy

### Minimum Required Permissions

Create an IAM policy with these permissions for the AWS user:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackEvents",
                "cloudformation:DescribeStackResources",
                "cloudformation:ValidateTemplate"
            ],
            "Resource": "arn:aws:cloudformation:*:*:stack/opsechat-*/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ecs:CreateCluster",
                "ecs:DeleteCluster",
                "ecs:DescribeClusters",
                "ecs:CreateService",
                "ecs:UpdateService",
                "ecs:DeleteService",
                "ecs:DescribeServices",
                "ecs:RegisterTaskDefinition",
                "ecs:DeregisterTaskDefinition",
                "ecs:DescribeTaskDefinition",
                "ecs:ListTasks",
                "ecs:DescribeTasks",
                "ecs:RunTask",
                "ecs:StopTask"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:CreateVpc",
                "ec2:DeleteVpc",
                "ec2:DescribeVpcs",
                "ec2:CreateSubnet",
                "ec2:DeleteSubnet",
                "ec2:DescribeSubnets",
                "ec2:CreateInternetGateway",
                "ec2:DeleteInternetGateway",
                "ec2:AttachInternetGateway",
                "ec2:DetachInternetGateway",
                "ec2:CreateNatGateway",
                "ec2:DeleteNatGateway",
                "ec2:DescribeNatGateways",
                "ec2:CreateRouteTable",
                "ec2:DeleteRouteTable",
                "ec2:DescribeRouteTables",
                "ec2:CreateRoute",
                "ec2:DeleteRoute",
                "ec2:AssociateRouteTable",
                "ec2:DisassociateRouteTable",
                "ec2:CreateSecurityGroup",
                "ec2:DeleteSecurityGroup",
                "ec2:DescribeSecurityGroups",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:AuthorizeSecurityGroupEgress",
                "ec2:RevokeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupEgress",
                "ec2:AllocateAddress",
                "ec2:ReleaseAddress",
                "ec2:DescribeAddresses",
                "ec2:DescribeAvailabilityZones"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:GetRole",
                "iam:PassRole",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:GetRolePolicy",
                "iam:TagRole",
                "iam:UntagRole"
            ],
            "Resource": [
                "arn:aws:iam::*:role/opsechat-*",
                "arn:aws:iam::*:role/ECS*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:CreateSecret",
                "secretsmanager:DeleteSecret",
                "secretsmanager:DescribeSecret",
                "secretsmanager:GetSecretValue",
                "secretsmanager:PutSecretValue",
                "secretsmanager:UpdateSecret",
                "secretsmanager:TagResource",
                "secretsmanager:UntagResource"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:opsechat-*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:DeleteLogGroup",
                "logs:DescribeLogGroups",
                "logs:PutRetentionPolicy",
                "logs:TagLogGroup",
                "logs:UntagLogGroup"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:/ecs/opsechat-*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:CreateRepository",
                "ecr:DeleteRepository",
                "ecr:DescribeRepositories",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload"
            ],
            "Resource": "*"
        }
    ]
}
```

### Creating the IAM User

1. **Create IAM User**
   ```bash
   aws iam create-user --user-name opsechat-deploy
   ```

2. **Create and Attach Policy**
   ```bash
   # Save the policy above as opsechat-policy.json
   aws iam create-policy \
     --policy-name OpSecChatDeployPolicy \
     --policy-document file://opsechat-policy.json
   
   aws iam attach-user-policy \
     --user-name opsechat-deploy \
     --policy-arn arn:aws:iam::ACCOUNT_ID:policy/OpSecChatDeployPolicy
   ```

3. **Create Access Keys**
   ```bash
   aws iam create-access-key --user-name opsechat-deploy
   ```

## Security Best Practices

### Secret Rotation

1. **Regular Rotation Schedule**
   - AWS keys: Every 90 days
   - GitHub tokens: Every 6 months
   - Docker Hub tokens: Every 6 months

2. **Automated Rotation Script**
   ```bash
   #!/bin/bash
   # rotate-secrets.sh
   
   echo "Rotating AWS access keys..."
   # Create new key
   NEW_KEY=$(aws iam create-access-key --user-name opsechat-deploy --output json)
   
   # Update GitHub secrets (requires GitHub CLI)
   gh secret set AWS_ACCESS_KEY_ID --body "$(echo $NEW_KEY | jq -r '.AccessKey.AccessKeyId')"
   gh secret set AWS_SECRET_ACCESS_KEY --body "$(echo $NEW_KEY | jq -r '.AccessKey.SecretAccessKey')"
   
   # Test new keys
   echo "Testing new keys..."
   aws sts get-caller-identity
   
   # Delete old key (after verification)
   # aws iam delete-access-key --user-name opsechat-deploy --access-key-id OLD_KEY_ID
   ```

### Access Monitoring

1. **CloudTrail Logging**
   ```bash
   aws cloudtrail create-trail \
     --name opsechat-api-trail \
     --s3-bucket-name opsechat-cloudtrail-logs
   
   aws cloudtrail start-logging --name opsechat-api-trail
   ```

2. **Access Alerts**
   ```bash
   # Create CloudWatch alarm for unusual API activity
   aws cloudwatch put-metric-alarm \
     --alarm-name "OpSecChat-UnusualAPIActivity" \
     --alarm-description "Alert on unusual AWS API activity" \
     --metric-name "APICallCount" \
     --namespace "AWS/CloudTrail" \
     --statistic "Sum" \
     --period 3600 \
     --threshold 100 \
     --comparison-operator "GreaterThanThreshold"
   ```

### Secret Validation

Create a validation script to test secrets:

```bash
#!/bin/bash
# validate-secrets.sh

echo "Validating AWS credentials..."
if aws sts get-caller-identity > /dev/null 2>&1; then
    echo "✅ AWS credentials valid"
else
    echo "❌ AWS credentials invalid"
    exit 1
fi

echo "Validating GitHub token..."
if curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user > /dev/null 2>&1; then
    echo "✅ GitHub token valid"
else
    echo "❌ GitHub token invalid or not set"
fi

echo "Validating Docker Hub credentials..."
if echo "$DOCKER_HUB_TOKEN" | docker login --username "$DOCKER_HUB_USERNAME" --password-stdin > /dev/null 2>&1; then
    echo "✅ Docker Hub credentials valid"
    docker logout
else
    echo "❌ Docker Hub credentials invalid or not set"
fi

echo "All validations complete"
```

## Environment-Specific Configuration

### Development Environment

```bash
# .env.development
AWS_ACCESS_KEY_ID=your_dev_key
AWS_SECRET_ACCESS_KEY=your_dev_secret
AWS_DEFAULT_REGION=us-east-1
ENVIRONMENT=development
TOR_CONTROL_HOST=127.0.0.1
TOR_CONTROL_PORT=9051
```

### Staging Environment

```bash
# GitHub Secrets for staging
AWS_ACCESS_KEY_ID_STAGING=your_staging_key
AWS_SECRET_ACCESS_KEY_STAGING=your_staging_secret
```

### Production Environment

```bash
# GitHub Secrets for production
AWS_ACCESS_KEY_ID_PRODUCTION=your_prod_key
AWS_SECRET_ACCESS_KEY_PRODUCTION=your_prod_secret
```

## Troubleshooting

### Common Issues

#### 1. Invalid AWS Credentials
```bash
# Test credentials
aws sts get-caller-identity

# Check permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT:user/opsechat-deploy \
  --action-names cloudformation:CreateStack \
  --resource-arns "*"
```

#### 2. GitHub Actions Failures
```bash
# Check secret availability in workflow
echo "AWS_ACCESS_KEY_ID is set: ${{ secrets.AWS_ACCESS_KEY_ID != '' }}"
```

#### 3. Permission Denied Errors
- Verify IAM policy includes required permissions
- Check resource ARN patterns match your resources
- Ensure user has policy attached

### Debug Commands

```bash
# List all secrets (names only)
gh secret list

# Test AWS CLI configuration
aws configure list

# Validate CloudFormation template
aws cloudformation validate-template \
  --template-body file://aws/cloudformation/opsechat-infrastructure.yml
```

## Backup and Recovery

### Secret Backup

```bash
#!/bin/bash
# backup-secrets.sh

# Create encrypted backup of secret names and metadata
gh secret list > secrets-backup-$(date +%Y%m%d).txt

# Backup IAM policy
aws iam get-user-policy \
  --user-name opsechat-deploy \
  --policy-name OpSecChatDeployPolicy > iam-policy-backup.json

echo "Backup completed. Store securely and encrypt."
```

### Recovery Process

1. **Recreate IAM User and Policy**
2. **Generate New Access Keys**
3. **Update Repository Secrets**
4. **Validate Configuration**
5. **Test Deployment Pipeline**

## Support

For issues with secret configuration:

1. **Check AWS Documentation**: https://docs.aws.amazon.com/IAM/
2. **GitHub Secrets Documentation**: https://docs.github.com/en/actions/security-guides/encrypted-secrets
3. **AWS CLI Configuration**: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html

Remember: Never commit secrets to version control. Always use environment variables or secret management systems.