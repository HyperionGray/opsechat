# AWS Deployment Guide for OpSecChat

## Overview

This guide provides comprehensive instructions for deploying OpSecChat to AWS while maintaining its security and anonymity characteristics. The deployment uses AWS ECS Fargate with a Tor proxy sidecar container to preserve the application's hidden service functionality.

## Prerequisites

### AWS Account Setup
1. **AWS Account**: Active AWS account with appropriate permissions
2. **AWS CLI**: Installed and configured with credentials
3. **Docker**: For building and pushing container images
4. **Git**: For cloning the repository

### Required AWS Permissions
Your AWS user/role needs the following permissions:
- CloudFormation: Full access for stack management
- ECS: Full access for container orchestration
- EC2: VPC and security group management
- IAM: Role and policy management
- Secrets Manager: Secret creation and access
- CloudWatch: Logging and monitoring
- ECR: Container registry access (if using ECR)

## Security Considerations

### Network Isolation
- **Private Subnets**: Application runs in private subnets with no direct internet access
- **NAT Gateway**: Outbound connections only through NAT for Tor network access
- **Security Groups**: Restrictive rules allowing only necessary traffic
- **No Load Balancer**: Maintains hidden service architecture

### Data Protection
- **Ephemeral Storage**: No persistent data storage (maintains anonymity)
- **Short Log Retention**: CloudWatch logs retained for only 7 days
- **Secrets Management**: Sensitive configuration stored in AWS Secrets Manager
- **Minimal Logging**: Respects application's anonymity requirements

### Tor Integration
- **Sidecar Pattern**: Tor proxy runs as separate container
- **Health Checks**: Ensures Tor is ready before starting application
- **Control Port Access**: Secure communication between app and Tor proxy

## Step-by-Step Deployment

### Step 1: Configure AWS Credentials

Set up AWS credentials in your repository secrets:

```bash
# In GitHub repository settings > Secrets and variables > Actions
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
```

Or configure locally:
```bash
aws configure
```

### Step 2: Build and Push Container Image

#### Option A: Using Amazon ECR
```bash
# Create ECR repository
aws ecr create-repository --repository-name opsechat --region us-east-1

# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and tag image
docker build -t opsechat:latest .
docker tag opsechat:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opsechat:latest

# Push image
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/opsechat:latest
```

#### Option B: Using Docker Hub
```bash
# Build and tag image
docker build -t your-dockerhub-username/opsechat:latest .

# Push to Docker Hub
docker push your-dockerhub-username/opsechat:latest
```

### Step 3: Deploy Infrastructure

Deploy the CloudFormation stacks in order:

#### 3.1 Deploy Network Infrastructure
```bash
aws cloudformation create-stack \
  --stack-name opsechat-infrastructure-staging \
  --template-body file://aws/cloudformation/opsechat-infrastructure.yml \
  --parameters ParameterKey=Environment,ParameterValue=staging \
  --region us-east-1
```

Wait for completion:
```bash
aws cloudformation wait stack-create-complete \
  --stack-name opsechat-infrastructure-staging \
  --region us-east-1
```

#### 3.2 Deploy ECS Service
```bash
aws cloudformation create-stack \
  --stack-name opsechat-ecs-staging \
  --template-body file://aws/cloudformation/opsechat-ecs.yml \
  --parameters \
    ParameterKey=Environment,ParameterValue=staging \
    ParameterKey=InfrastructureStackName,ParameterValue=opsechat-infrastructure-staging \
    ParameterKey=ContainerImage,ParameterValue=your-image-uri \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

### Step 4: Configure Secrets

Update the secrets in AWS Secrets Manager:

```bash
# Generate a secure Flask secret key
FLASK_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

# Update secrets
aws secretsmanager update-secret \
  --secret-id opsechat-secrets-staging \
  --secret-string "{
    \"TOR_CONTROL_HOST\": \"localhost\",
    \"TOR_CONTROL_PORT\": \"9051\",
    \"FLASK_SECRET_KEY\": \"$FLASK_SECRET\",
    \"ENVIRONMENT\": \"staging\"
  }" \
  --region us-east-1
```

### Step 5: Run ECS Service

Create and run the ECS service:

```bash
# Get cluster and task definition ARNs from CloudFormation outputs
CLUSTER_NAME=$(aws cloudformation describe-stacks \
  --stack-name opsechat-ecs-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' \
  --output text \
  --region us-east-1)

TASK_DEFINITION_ARN=$(aws cloudformation describe-stacks \
  --stack-name opsechat-ecs-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`TaskDefinitionArn`].OutputValue' \
  --output text \
  --region us-east-1)

SECURITY_GROUP_ID=$(aws cloudformation describe-stacks \
  --stack-name opsechat-ecs-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`SecurityGroupId`].OutputValue' \
  --output text \
  --region us-east-1)

SUBNET_1=$(aws cloudformation describe-stacks \
  --stack-name opsechat-infrastructure-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnet1Id`].OutputValue' \
  --output text \
  --region us-east-1)

SUBNET_2=$(aws cloudformation describe-stacks \
  --stack-name opsechat-infrastructure-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnet2Id`].OutputValue' \
  --output text \
  --region us-east-1)

# Create ECS service
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name opsechat-service \
  --task-definition $TASK_DEFINITION_ARN \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[$SUBNET_1,$SUBNET_2],
    securityGroups=[$SECURITY_GROUP_ID],
    assignPublicIp=DISABLED
  }" \
  --region us-east-1
```

## Monitoring and Maintenance

### CloudWatch Logs
View application logs:
```bash
aws logs describe-log-streams \
  --log-group-name /ecs/opsechat-staging \
  --region us-east-1

aws logs get-log-events \
  --log-group-name /ecs/opsechat-staging \
  --log-stream-name opsechat-app/opsechat-app/TASK_ID \
  --region us-east-1
```

### Health Monitoring
Check service status:
```bash
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services opsechat-service \
  --region us-east-1
```

### Accessing the Hidden Service
The application will create a Tor hidden service and log the .onion address. To find it:

```bash
# Check application logs for the hidden service address
aws logs filter-log-events \
  --log-group-name /ecs/opsechat-staging \
  --filter-pattern "Started a new hidden service" \
  --region us-east-1
```

## Production Deployment

For production deployment:

1. **Change Environment Parameter**: Use `production` instead of `staging`
2. **Increase Resources**: Consider larger CPU/memory allocation
3. **Enable Container Insights**: For detailed monitoring
4. **Set up Alarms**: CloudWatch alarms for service health
5. **Backup Secrets**: Ensure secrets are backed up securely
6. **Review Security Groups**: Minimize access further if possible

### Production Example
```bash
aws cloudformation create-stack \
  --stack-name opsechat-infrastructure-production \
  --template-body file://aws/cloudformation/opsechat-infrastructure.yml \
  --parameters ParameterKey=Environment,ParameterValue=production \
  --region us-east-1
```

## Troubleshooting

### Common Issues

#### 1. Task Fails to Start
- Check CloudWatch logs for error messages
- Verify secrets are properly configured
- Ensure container image is accessible

#### 2. Tor Connection Issues
- Verify NAT Gateway is properly configured
- Check security group rules
- Review Tor proxy container logs

#### 3. Service Discovery Problems
- Ensure health checks are passing
- Verify network configuration
- Check task definition dependencies

### Debug Commands
```bash
# List running tasks
aws ecs list-tasks --cluster $CLUSTER_NAME --region us-east-1

# Describe specific task
aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks TASK_ARN --region us-east-1

# Check service events
aws ecs describe-services --cluster $CLUSTER_NAME --services opsechat-service --region us-east-1
```

## Cost Optimization

### Estimated Monthly Costs (us-east-1)
- **Fargate Task (512 CPU, 1GB RAM)**: ~$15-30/month
- **NAT Gateway**: ~$45/month
- **CloudWatch Logs**: ~$1-5/month
- **Secrets Manager**: ~$0.40/month
- **Total**: ~$60-80/month

### Cost Reduction Strategies
1. **Use Fargate Spot**: 50-70% cost reduction
2. **Optimize Task Size**: Right-size CPU/memory
3. **Reduce Log Retention**: Shorter retention periods
4. **Schedule Tasks**: Run only when needed

## Security Hardening

### Additional Security Measures
1. **VPC Flow Logs**: Monitor network traffic
2. **AWS Config**: Track configuration changes
3. **GuardDuty**: Threat detection
4. **Security Hub**: Centralized security findings
5. **WAF**: Web application firewall (if exposing HTTP)

### Compliance Considerations
- **Data Residency**: Choose appropriate AWS region
- **Encryption**: Enable encryption at rest and in transit
- **Access Logging**: Monitor who accesses the system
- **Audit Trail**: CloudTrail for API activity

## Cleanup

To remove all AWS resources:

```bash
# Delete ECS service first
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service opsechat-service \
  --desired-count 0 \
  --region us-east-1

aws ecs delete-service \
  --cluster $CLUSTER_NAME \
  --service opsechat-service \
  --region us-east-1

# Delete CloudFormation stacks
aws cloudformation delete-stack \
  --stack-name opsechat-ecs-staging \
  --region us-east-1

aws cloudformation delete-stack \
  --stack-name opsechat-infrastructure-staging \
  --region us-east-1

# Delete ECR repository (if used)
aws ecr delete-repository \
  --repository-name opsechat \
  --force \
  --region us-east-1
```

## Support and Documentation

- **AWS ECS Documentation**: https://docs.aws.amazon.com/ecs/
- **AWS Fargate Documentation**: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
- **Tor Project Documentation**: https://www.torproject.org/docs/
- **OpSecChat Repository**: https://github.com/HyperionGray/opsechat

For issues specific to AWS deployment, please check CloudWatch logs and AWS service health dashboards before opening issues.