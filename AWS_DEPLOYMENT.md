# AWS Deployment Guide for opsechat

## Overview

This guide provides comprehensive instructions for deploying opsechat on Amazon Web Services (AWS) with proper Tor networking configuration and security hardening.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed locally
- Basic understanding of AWS networking concepts
- Tor daemon knowledge for hidden service configuration

## Deployment Options

### Option 1: ECS with Fargate (Recommended for Production)

#### 1.1 VPC and Networking Setup

```bash
# Create VPC for opsechat deployment
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=opsechat-vpc}]'

# Create public subnet for NAT Gateway
aws ec2 create-subnet --vpc-id vpc-xxxxx --cidr-block 10.0.1.0/24 --availability-zone us-east-1a

# Create private subnet for ECS tasks
aws ec2 create-subnet --vpc-id vpc-xxxxx --cidr-block 10.0.2.0/24 --availability-zone us-east-1a
```

#### 1.2 Security Groups Configuration

```bash
# Create security group for opsechat
aws ec2 create-security-group --group-name opsechat-sg --description "Security group for opsechat" --vpc-id vpc-xxxxx

# Allow Tor control port (internal only)
aws ec2 authorize-security-group-ingress --group-id sg-xxxxx --protocol tcp --port 9051 --source-group sg-xxxxx

# Allow HTTP traffic (for container health checks)
aws ec2 authorize-security-group-ingress --group-id sg-xxxxx --protocol tcp --port 5000 --source-group sg-xxxxx
```

#### 1.3 ECS Cluster and Task Definition

Create `ecs-task-definition.json`:

```json
{
  "family": "opsechat-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/opsechatTaskRole",
  "containerDefinitions": [
    {
      "name": "tor-proxy",
      "image": "dperson/torproxy:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 9050,
          "protocol": "tcp"
        },
        {
          "containerPort": 9051,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "TOR_CONTROL_PORT",
          "value": "9051"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/opsechat",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "tor"
        }
      }
    },
    {
      "name": "opsechat-app",
      "image": "your-account.dkr.ecr.us-east-1.amazonaws.com/opsechat:latest",
      "essential": true,
      "dependsOn": [
        {
          "containerName": "tor-proxy",
          "condition": "START"
        }
      ],
      "environment": [
        {
          "name": "TOR_CONTROL_HOST",
          "value": "127.0.0.1"
        },
        {
          "name": "TOR_CONTROL_PORT",
          "value": "9051"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/opsechat",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "app"
        }
      }
    }
  ]
}
```

### Option 2: EKS Deployment

#### 2.1 Kubernetes Manifests

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opsechat-deployment
  namespace: opsechat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: opsechat
  template:
    metadata:
      labels:
        app: opsechat
    spec:
      containers:
      - name: tor-proxy
        image: dperson/torproxy:latest
        ports:
        - containerPort: 9050
        - containerPort: 9051
        env:
        - name: TOR_CONTROL_PORT
          value: "9051"
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
      - name: opsechat-app
        image: your-registry/opsechat:latest
        env:
        - name: TOR_CONTROL_HOST
          value: "127.0.0.1"
        - name: TOR_CONTROL_PORT
          value: "9051"
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: opsechat-service
  namespace: opsechat
spec:
  selector:
    app: opsechat
  ports:
  - port: 80
    targetPort: 5000
  type: ClusterIP
```

### Option 3: EC2 with Docker Compose

#### 3.1 EC2 Instance Setup

```bash
# Launch EC2 instance with appropriate security group
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.medium \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxx \
  --subnet-id subnet-xxxxx \
  --user-data file://user-data.sh
```

#### 3.2 User Data Script (`user-data.sh`)

```bash
#!/bin/bash
yum update -y
yum install -y docker git

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Start Docker service
systemctl start docker
systemctl enable docker

# Clone and deploy opsechat
cd /opt
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
./compose-up.sh
```

## Security Hardening

### 1. IAM Roles and Policies

#### ECS Task Role Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/ecs/opsechat:*"
    }
  ]
}
```

### 2. Network Security

#### Security Group Rules (Restrictive)

```bash
# Remove default rules and add only necessary ones
aws ec2 revoke-security-group-egress --group-id sg-xxxxx --protocol -1 --port -1 --cidr 0.0.0.0/0

# Allow HTTPS outbound for Tor directory servers
aws ec2 authorize-security-group-egress --group-id sg-xxxxx --protocol tcp --port 443 --cidr 0.0.0.0/0

# Allow Tor network ports
aws ec2 authorize-security-group-egress --group-id sg-xxxxx --protocol tcp --port 9001-9030 --cidr 0.0.0.0/0
```

### 3. Secrets Management

#### Using AWS Secrets Manager

```bash
# Store sensitive configuration
aws secretsmanager create-secret \
  --name "opsechat/config" \
  --description "opsechat configuration secrets" \
  --secret-string '{"smtp_password":"your-password","api_keys":"your-keys"}'
```

#### Update task definition to use secrets:

```json
{
  "secrets": [
    {
      "name": "SMTP_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:region:account:secret:opsechat/config:smtp_password::"
    }
  ]
}
```

## Monitoring and Logging

### 1. CloudWatch Configuration

#### Log Groups Setup

```bash
# Create log group for opsechat
aws logs create-log-group --log-group-name /ecs/opsechat

# Set retention policy
aws logs put-retention-policy --log-group-name /ecs/opsechat --retention-in-days 30
```

### 2. CloudWatch Alarms

```bash
# Create alarm for high CPU usage
aws cloudwatch put-metric-alarm \
  --alarm-name "opsechat-high-cpu" \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

## Networking Considerations for Tor

### 1. Tor Hidden Service Requirements

- **Persistent Control Port Access**: Tor control port (9051) must be accessible within the container network
- **Directory Server Access**: Containers need HTTPS access to Tor directory servers
- **Hidden Service Persistence**: For production, consider persistent Tor data directory

### 2. Container Networking Best Practices

```yaml
# Docker Compose networking for Tor
version: '3.8'
services:
  tor:
    image: dperson/torproxy:latest
    networks:
      - tor-network
    ports:
      - "9050:9050"
      - "9051:9051"
    
  opsechat:
    build: .
    depends_on:
      - tor
    networks:
      - tor-network
    environment:
      - TOR_CONTROL_HOST=tor
      - TOR_CONTROL_PORT=9051

networks:
  tor-network:
    driver: bridge
```

## Troubleshooting

### Common Issues

1. **Tor Connection Failed**
   - Check security group allows port 9051
   - Verify Tor container is running and healthy
   - Check network connectivity between containers

2. **Hidden Service Creation Timeout**
   - Increase timeout values in application
   - Check Tor directory server connectivity
   - Verify Tor configuration is correct

3. **Container Health Check Failures**
   - Adjust health check intervals
   - Check application startup time
   - Verify port mappings are correct

### Debugging Commands

```bash
# Check ECS task logs
aws logs get-log-events --log-group-name /ecs/opsechat --log-stream-name ecs/opsechat-app/task-id

# Test Tor connectivity
docker exec -it container-id curl --socks5 127.0.0.1:9050 https://check.torproject.org/

# Check hidden service status
docker exec -it tor-container cat /var/lib/tor/hidden_service/hostname
```

## Cost Optimization

### 1. Resource Sizing

- **Fargate**: Use smallest viable CPU/memory allocation
- **EC2**: Consider Spot instances for development
- **Storage**: Use ephemeral storage where possible

### 2. Monitoring Costs

```bash
# Set up billing alerts
aws budgets create-budget \
  --account-id 123456789012 \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

## Security Checklist

- [ ] VPC with private subnets configured
- [ ] Security groups restrict unnecessary access
- [ ] IAM roles follow least privilege principle
- [ ] Secrets stored in AWS Secrets Manager
- [ ] CloudWatch logging enabled
- [ ] Network ACLs configured appropriately
- [ ] Container images scanned for vulnerabilities
- [ ] Tor configuration hardened
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures documented

## Next Steps

1. **Test Deployment**: Deploy in development environment first
2. **Security Review**: Conduct security assessment of deployed infrastructure
3. **Performance Testing**: Validate performance under expected load
4. **Monitoring Setup**: Configure comprehensive monitoring and alerting
5. **Documentation**: Update operational procedures and runbooks

For additional support, refer to the main [README.md](README.md) and [SECURITY.md](SECURITY.md) documentation.