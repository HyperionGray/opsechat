# PacketFS Unified Compute - Deployment Guide

Deploy the planetary-scale distributed compute system step-by-step.

## Prerequisites

- [ ] AWS account with Lambda access
- [ ] Cloudflare account with Workers enabled
- [ ] Fly.io account with CLI installed
- [ ] Redis instance (local development) or managed Redis (production)
- [ ] Git and Docker installed locally

## Phase 1: Local Development & Testing

### 1. Set up local Redis

```bash
# Using Docker
docker run -d -p 6379:6379 --name redis redis:alpine

# Or use Homebrew (macOS)
brew install redis
redis-server
```

### 2. Install dependencies

```bash
cd /home/punk/Projects/packetfs/unified-compute

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Test the dispatcher locally

```bash
# Terminal 1: Start the dispatcher
python3 dispatcher.py

# Terminal 2: Run tests
python3 test_dispatcher.py
```

Expected output:
```
TEST 1: Single Job Execution
  Job ID: ...
  Status: Submitted
  Result:
    Substrate: browser_wasm
    Success: False (expected - no actual substrates yet)
    ...
```

## Phase 2: Deploy Cloudflare Worker

### 1. Set up Cloudflare project

```bash
mkdir cloudflare-worker
cd cloudflare-worker

# Install wrangler
npm install -g @cloudflare/wrangler@latest

# Login to Cloudflare
wrangler login
```

### 2. Create wrangler.toml

```toml
name = "packetfs-compute"
type = "javascript"
main = "src/worker.ts"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]

[env.production]
routes = [
  { pattern = "packetfs-compute.example.com/*", zone_name = "example.com" }
]
```

### 3. Compile TypeScript worker

```bash
# Copy worker code
cp ../cloudflare-worker.ts src/worker.ts

# Build
npm run build
```

### 4. Deploy to Cloudflare

```bash
# Publish to production
wrangler publish --env production

# Check deployment
curl https://packetfs-compute.example.com/health
```

**Output from deployment:**
```
Deployed to: https://packetfs-compute.example.com
```

Save the worker URL for later integration.

## Phase 3: Deploy AWS Lambda

### 1. Create Lambda function

```bash
# Create function directory
mkdir lambda-function
cd lambda-function

# Copy handler
cp ../lambda-handler.py index.py

# Install dependencies
pip install -r ../requirements.txt -t .

# Create deployment package
zip -r function.zip .
```

### 2. Deploy via AWS CLI

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# Create IAM role
aws iam create-role \
  --role-name packetfs-lambda-role \
  --assume-role-policy-document file:///dev/stdin <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create function
aws lambda create-function \
  --function-name packetfs-compute \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/packetfs-lambda-role \
  --handler index.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 512

# Create function URL
aws lambda create-function-url-config \
  --function-name packetfs-compute \
  --auth-type NONE
```

**Output:**
```
FunctionUrl: https://YOUR_LAMBDA_URL.lambda-url.us-east-1.on.aws/
```

Save the Lambda URL for dispatcher integration.

### 3. Test Lambda locally

```bash
# Using SAM (AWS Serverless Application Model)
sam local start-api

# In another terminal, test
curl -X POST http://localhost:3000/compute \
  -H "Content-Type: application/json" \
  -d '{
    "jobId": "test-1",
    "program": {
      "op": "counteq",
      "data_url": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/pdf-1.pdf",
      "offset": 0,
      "length": 1024,
      "imm": 42
    }
  }'
```

## Phase 4: Deploy Fly.io

### 1. Install Fly CLI

```bash
# macOS
brew install flyctl

# Or download from https://fly.io/docs/hands-on/install-flyctl/
```

### 2. Initialize Fly app

```bash
cd /home/punk/Projects/packetfs/unified-compute

# Login to Fly
fly auth login

# Launch app
fly launch \
  --name packetfs-compute \
  --region iad \
  --no-deploy
```

### 3. Configure Redis on Fly.io

```bash
# Create managed Redis
fly redis create \
  --name packetfs-redis \
  --region iad

# Get connection string
fly redis status packetfs-redis
```

Update `fly.toml`:
```toml
[env]
  REDIS_URL = "redis://:PASSWORD@HOST:PORT"
```

### 4. Deploy to Fly.io

```bash
# Deploy
fly deploy

# Check status
fly status

# View logs
fly logs

# Scale up if needed
fly scale count app=3
```

**Output:**
```
Deployment complete
App URL: https://packetfs-compute.fly.dev
```

## Phase 5: Browser Runtime CDN

### 1. Upload to Cloud Storage

```bash
# Using Google Cloud Storage
gsutil mb gs://packetfs-cdn
gsutil -h "Cache-Control:public, max-age=3600" \
  cp browser-runtime.js \
  gs://packetfs-cdn/v1/browser-runtime.js

# Make public
gsutil acl ch -u AllUsers:R gs://packetfs-cdn/v1/browser-runtime.js

# Access via: https://storage.googleapis.com/packetfs-cdn/v1/browser-runtime.js
```

Or use Cloudflare:
```bash
# Upload to Cloudflare Pages
cd browser-cdn
wrangler pages publish ./
```

### 2. Create test page

```bash
cat > browser-test.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
  <title>PacketFS Browser Compute Test</title>
</head>
<body>
  <h1>PacketFS Browser Compute</h1>
  <button onclick="testCompute()">Execute Job</button>
  <pre id="output"></pre>
  
  <script>
    window.PACKETFS_AUTO_INIT = true;
  </script>
  <script src="https://storage.googleapis.com/packetfs-cdn/v1/browser-runtime.js"></script>
  
  <script>
    async function testCompute() {
      const compute = new PacketFSBrowserCompute('/packetfs-sw.js');
      await compute.initialize();
      
      const result = await compute.submitJob({
        op: 'fnv64',
        data_url: 'https://www.w3.org/WAI/WCAG21/Techniques/pdf/pdf-1.pdf'
      });
      
      document.getElementById('output').textContent = JSON.stringify(result, null, 2);
    }
  </script>
</body>
</html>
EOF

# Deploy
python3 -m http.server 8000
# Open http://localhost:8000/browser-test.html
```

## Phase 6: Connect Dispatcher to All Substrates

### 1. Update dispatcher environment variables

```bash
export CLOUDFLARE_API_TOKEN="your_cloudflare_token"
export CLOUDFLARE_WORKER_URL="https://packetfs-compute.example.com"

export AWS_ACCESS_KEY_ID="your_aws_key"
export AWS_SECRET_ACCESS_KEY="your_aws_secret"
export AWS_LAMBDA_URL="https://YOUR_LAMBDA_URL.lambda-url.us-east-1.on.aws"

export FLY_API_TOKEN="your_fly_token"
export FLY_APP_NAME="packetfs-compute"

export SERVICE_WORKER_URL="https://packetfs-browser.example.com"

export REDIS_URL="redis://localhost:6379"
```

### 2. Test integrated dispatcher

```bash
# Start dispatcher
python3 dispatcher.py

# Submit job that routes through all substrates
python3 -c "
import asyncio
from dispatcher import ComputeDispatcher, ComputeJob

async def test():
    d = ComputeDispatcher()
    await d.initialize()
    
    job = ComputeJob(
        program={
            'op': 'counteq',
            'data_url': 'https://www.w3.org/WAI/WCAG21/Techniques/pdf/pdf-1.pdf',
            'imm': 42
        }
    )
    
    result = await d.dispatch_job(job)
    print(f'Executed on: {result.substrate_type.value}')
    print(f'Time: {result.execution_time_ms:.1f}ms')
    print(f'Cost: \${result.cost_usd:.4f}')
    
    await d.shutdown()

asyncio.run(test())
"
```

## Phase 7: Production Hardening

### 1. Set up monitoring

```bash
# Enable Cloudflare Analytics
# - Dashboard > Analytics

# Enable Lambda CloudWatch
# - AWS Console > Lambda > Monitoring

# Enable Fly.io Metrics
fly metrics show
```

### 2. Set up alerting

```bash
# CloudWatch alarm for Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name packetfs-lambda-errors \
  --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT:alerts \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

### 3. Enable auto-scaling

```bash
# Fly.io already has auto-scaling in fly.toml

# Lambda auto-scaling via Application Auto Scaling
aws application-autoscaling register-scalable-target \
  --service-namespace lambda \
  --resource-id function:packetfs-compute:provisioned-concurrent-executions \
  --scalable-dimension lambda:function:ProvisionedConcurrentExecutions \
  --min-capacity 10 \
  --max-capacity 100
```

## Phase 8: Deploy to Production

### 1. Point DNS

```bash
# Create CNAME records
# packetfs-compute.example.com → cloudflare-worker
# dispatcher.example.com → fly.io-app.fly.dev
```

### 2. Enable HTTPS

```bash
# Cloudflare: Automatic (free)
# Fly.io: fly certs create packetfs-compute.example.com
```

### 3. Final verification

```bash
# Check all endpoints
curl https://packetfs-compute.example.com/health
curl https://dispatcher.example.com/health
curl https://packetfs-browser.example.com/health

# Submit test job
curl -X POST https://dispatcher.example.com/compute \
  -H "Content-Type: application/json" \
  -d '{
    "jobId": "prod-test-1",
    "program": {
      "op": "fnv64",
      "data_url": "https://example.com/data.bin"
    }
  }'
```

## Troubleshooting

### Cloudflare Worker not responding
```bash
# Check deployment
wrangler list

# View logs
wrangler tail

# Redeploy
wrangler publish
```

### Lambda function errors
```bash
# View CloudWatch logs
aws logs tail /aws/lambda/packetfs-compute --follow

# Test locally
sam local invoke -e test-event.json

# Check permissions
aws lambda get-policy --function-name packetfs-compute
```

### Fly.io app crashes
```bash
# Check logs
fly logs -a packetfs-compute

# SSH into app
fly ssh console -a packetfs-compute

# Restart
fly apps restart packetfs-compute
```

### Redis connection issues
```bash
# Test connection
redis-cli -h localhost -p 6379 PING

# Check Fly.io Redis
fly redis status packetfs-redis

# View connection string
fly redis status packetfs-redis --full
```

## Success Checklist

- [ ] Local dispatcher runs and passes tests
- [ ] Cloudflare Worker deployed and responds
- [ ] AWS Lambda deployed and executes jobs
- [ ] Fly.io app running with auto-scaling
- [ ] Browser runtime accessible via CDN
- [ ] Dispatcher selects all substrates
- [ ] End-to-end job routing works
- [ ] Metrics dashboard online
- [ ] Production DNS configured
- [ ] Monitoring/alerting active
- [ ] HTTPS on all endpoints

## Next Steps

1. **Expand substrates:**
   - Vercel Edge Functions
   - GCP Cloud Run
   - Volunteer computing network

2. **Optimize:**
   - Profile each substrate
   - Fine-tune selection algorithm
   - Reduce cold start times

3. **Scale:**
   - Deploy browsers to websites
   - Recruit volunteers
   - Handle millions of concurrent jobs

🚀 You're live! Monitor, optimize, scale.
