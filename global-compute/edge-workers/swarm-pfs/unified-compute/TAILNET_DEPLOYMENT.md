# PacketFS on Tailnet - Deploy to Your Private Network

Turn your Tailscale network into a private supercomputer. All compute nodes join your Tailnet and communicate securely over WireGuard.

## Why This is Awesome

- **Zero trust networking** - All nodes encrypted via Tailscale
- **Private cluster** - Not exposed to public internet
- **Tailnet integration** - Use Tailscale DNS names
- **Global reach** - Nodes can be anywhere on your Tailnet
- **One command deploy** - `tailscale share` + our dispatcher

---

## Prerequisites

✓ Tailscale installed (`/usr/bin/tailscale`)
✓ AWS CLI available
✓ Redis (local or managed)
✓ Python 3.11+

---

## Step 1: Create Tailnet Auth Key

```bash
# Get your Tailnet name
tailscale status | grep -i "your tailnet"

# Generate auth key (one-time use)
tailscale authkey create --reusable --preauthorized

# Save as environment variable
export TAILSCALE_AUTH_KEY="tskey-auth-xxxxxxxxxxxx"
```

---

## Step 2: Deploy Dispatcher to Your Tailnet (Local)

### Option A: Run locally on your machine

```bash
# Ensure Tailscale is connected
tailscale status

# Install dependencies
cd /home/punk/Projects/packetfs/unified-compute
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up environment
export REDIS_URL="redis://localhost:6379"
export TAILSCALE_AUTH_KEY="tskey-auth-xxxxxxxxxxxx"

# Start Redis (if local)
docker run -d -p 6379:6379 redis:alpine

# Export dispatcher IP on Tailnet
export DISPATCHER_IP=$(tailscale ip -4)
echo "Dispatcher accessible at: http://$DISPATCHER_IP:8080"

# Start dispatcher
python3 dispatcher.py --host 0.0.0.0 --port 8080

# In another terminal, verify it's on Tailnet
curl http://$(tailscale ip -4):8080/health
```

### Option B: Deploy to EC2 instance on Tailnet

```bash
# Launch EC2 instance (Ubuntu 22.04)
aws ec2 run-instances \
  --image-ids ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --security-groups default \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=packetfs-dispatcher}]'

# Note instance ID, then SSH into it
INSTANCE_ID="i-0123456789abcdef0"
aws ec2 wait instance-running --instance-ids $INSTANCE_ID

# Get instance IP
INSTANCE_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)

# SSH and install
ssh -i your-key.pem ubuntu@$INSTANCE_IP

# On the instance:
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --authkey=$TAILSCALE_AUTH_KEY

# Install PacketFS
git clone https://github.com/your-repo/packetfs.git
cd packetfs/unified-compute
pip3 install -r requirements.txt

# Start dispatcher
python3 dispatcher.py --host 0.0.0.0 --port 8080

# On your local machine, verify via Tailnet DNS
curl http://packetfs-dispatcher:8080/health
```

---

## Step 3: Deploy Compute Nodes to Tailnet

### Cloudflare Worker (Already Global)

```bash
# Deploy with your Tailnet dispatcher as backend
cd cloudflare-worker

# Create wrangler.toml pointing to Tailnet
cat > wrangler.toml << 'EOF'
name = "packetfs-compute"
type = "javascript"
main = "src/worker.ts"
compatibility_date = "2024-01-01"

[env.production]
vars = { DISPATCHER_URL = "http://packetfs-dispatcher:8080" }
EOF

# Note: Cloudflare Workers can't directly access private Tailnets
# Instead, route through a public endpoint or use HTTP tunnel
```

### AWS Lambda (Quick Deploy)

```bash
# Create Lambda that joins Tailnet
mkdir -p lambda-tailnet
cd lambda-tailnet

# Dockerfile for Lambda runtime with Tailscale
cat > Dockerfile << 'EOF'
FROM public.ecr.aws/lambda/python:3.11

# Install Tailscale
RUN yum install -y tailscale

# Copy handler
COPY lambda-handler.py ${LAMBDA_TASK_ROOT}
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Set handler
CMD [ "lambda-handler.lambda_handler" ]
EOF

# Build and push to ECR
aws ecr create-repository --repository-name packetfs-compute || true
aws ecr get-login-password | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

docker build -t packetfs-compute .
docker tag packetfs-compute:latest $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/packetfs-compute:latest
docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/packetfs-compute:latest

# Create Lambda function from image
aws lambda create-function \
  --function-name packetfs-compute \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-role \
  --code ImageUri=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/packetfs-compute:latest \
  --package-type Image \
  --timeout 30 \
  --memory-size 512 \
  --environment Variables="{TAILSCALE_AUTH_KEY=$TAILSCALE_AUTH_KEY,DISPATCHER_URL=http://packetfs-dispatcher:8080}"
```

### EC2 Compute Nodes (On Tailnet)

```bash
# Launch multiple compute instances
for i in {1..5}; do
  aws ec2 run-instances \
    --image-ids ami-0c55b159cbfafe1f0 \
    --instance-type t3.micro \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=packetfs-compute-$i}]" &
done

# On each instance (via SSH):
sudo -i

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey=$TAILSCALE_AUTH_KEY

# Install PacketFS compute runtime
apt-get update
apt-get install -y python3-pip python3-venv
git clone https://github.com/your-repo/packetfs.git
cd packetfs/unified-compute
pip3 install -r requirements.txt

# Create Tailnet-aware worker
cat > tailnet-worker.py << 'PYTHON'
#!/usr/bin/env python3
import asyncio
from dispatcher import ComputeDispatcher, ComputeJob
import socket

# Get this node's Tailnet IP
def get_tailnet_ip():
    return socket.gethostbyname(socket.gethostname())

async def worker_loop():
    dispatcher_url = "http://packetfs-dispatcher:8080"
    node_ip = get_tailnet_ip()
    
    print(f"🌐 PacketFS Compute Node on Tailnet: {node_ip}")
    
    # Connect to dispatcher via Tailnet
    dispatcher = ComputeDispatcher(redis_url="redis://packetfs-redis:6379")
    await dispatcher.initialize()
    
    # Process jobs continuously
    try:
        await dispatcher.process_queue()
    except KeyboardInterrupt:
        print("Shutting down...")
        await dispatcher.shutdown()

asyncio.run(worker_loop())
PYTHON

chmod +x tailnet-worker.py

# Start worker
nohup ./tailnet-worker.py > /var/log/packetfs-worker.log 2>&1 &
```

### Browser Nodes (On Tailnet via Dashboard)

```html
<!-- Create test page accessible via Tailnet -->
<!-- Serve via: python3 -m http.server 8000 on a Tailnet node -->

<!DOCTYPE html>
<html>
<head>
  <title>PacketFS Browser Node - Tailnet</title>
</head>
<body>
  <h1>PacketFS Browser Compute Node</h1>
  <p>Connected to Tailnet: <span id="status">Connecting...</span></p>
  <button onclick="submitJob()">Execute Job</button>
  <pre id="output"></pre>
  
  <script>
    // Get Tailnet DNS info
    fetch('http://packetfs-dispatcher:8080/health')
      .then(r => r.json())
      .then(d => {
        document.getElementById('status').textContent = 'Connected to dispatcher at ' + d.edge_location;
      });
    
    async function submitJob() {
      const result = await fetch('http://packetfs-dispatcher:8080/compute', {
        method: 'POST',
        body: JSON.stringify({
          jobId: 'browser-' + Date.now(),
          program: {
            op: 'fnv64',
            data_url: 'https://example.com/data.bin'
          }
        })
      }).then(r => r.json());
      
      document.getElementById('output').textContent = JSON.stringify(result, null, 2);
    }
  </script>
</body>
</html>
```

---

## Step 4: Monitor Tailnet Cluster

```bash
# See all your Tailnet nodes
tailscale status

# Check which nodes are compute nodes
tailscale status | grep packetfs

# SSH into any node via Tailnet DNS
ssh ubuntu@packetfs-compute-1

# Monitor dispatcher health
curl http://packetfs-dispatcher:8080/health | jq

# Watch metrics in real-time
watch -n 1 'curl -s http://packetfs-dispatcher:8080/metrics | tail -20'
```

---

## Step 5: Submit Jobs to Your Cluster

### From Python

```python
import asyncio
from dispatcher import ComputeDispatcher, ComputeJob

async def submit_to_tailnet():
    # Dispatcher is at packetfs-dispatcher:8080 on your Tailnet
    dispatcher = ComputeDispatcher(redis_url="redis://packetfs-redis:6379")
    await dispatcher.initialize()
    
    # Submit jobs
    for i in range(10):
        job = ComputeJob(
            program={
                'op': 'fnv64',
                'data_url': 'https://www.w3.org/WAI/WCAG21/Techniques/pdf/pdf-1.pdf'
            }
        )
        job_id = await dispatcher.submit_job(job)
        print(f"Job {i+1} submitted: {job_id}")
    
    # Process queue
    await dispatcher.process_queue()

asyncio.run(submit_to_tailnet())
```

### From Redis CLI (On Tailnet)

```bash
# Connect to Redis on Tailnet
redis-cli -h packetfs-redis -p 6379

# Submit job
lpush packetfs:jobs:queue '{
  "job_id": "tailnet-test-1",
  "program": {
    "op": "counteq",
    "data_url": "https://example.com/data",
    "imm": 42
  }
}'

# Check result
get "packetfs:results:tailnet-test-1"
```

### From curl (On Tailnet)

```bash
# Submit job to dispatcher on Tailnet
curl -X POST http://packetfs-dispatcher:8080/compute \
  -H "Content-Type: application/json" \
  -d '{
    "jobId": "tailnet-curl-1",
    "program": {
      "op": "fnv64",
      "data_url": "https://example.com/data.bin"
    }
  }'
```

---

## Step 6: Scale Up Gradually

### Start Small
1. Dispatcher on local machine or EC2
2. 1-2 compute nodes
3. 10 browser nodes

### Monitor
```bash
# Watch metrics
watch -n 5 'curl -s http://packetfs-dispatcher:8080/metrics'

# Check logs
journalctl -u packetfs-dispatcher -f

# Monitor Tailnet traffic
tailscale netcheck
```

### Scale Up
```bash
# Launch more EC2 nodes
for i in {6..20}; do
  aws ec2 run-instances \
    --image-ids ami-0c55b159cbfafe1f0 \
    --instance-type t3.micro \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=packetfs-compute-$i}]" &
done

# Verify they join
watch tailscale status | grep packetfs
```

---

## Quick Start Command (TL;DR)

```bash
# 1. Get auth key
export TAILSCALE_AUTH_KEY=$(tailscale authkey create --reusable --preauthorized)

# 2. Start dispatcher locally
cd /home/punk/Projects/packetfs/unified-compute
docker run -d -p 6379:6379 redis:alpine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 dispatcher.py --host 0.0.0.0 --port 8080

# 3. Verify on Tailnet
curl http://$(tailscale ip -4):8080/health

# 4. Submit test job
python3 -c "
import asyncio
from dispatcher import ComputeDispatcher, ComputeJob

async def test():
    d = ComputeDispatcher()
    await d.initialize()
    job = ComputeJob(program={'op': 'fnv64', 'data_url': 'https://example.com/data'})
    result = await d.dispatch_job(job)
    print(f'Job executed: {result.substrate_type.value}')
    await d.shutdown()

asyncio.run(test())
"

# 5. Watch nodes join via
tailscale status --verbose
```

---

## Tailnet Security Benefits

- **Zero Trust** - All traffic encrypted via WireGuard
- **Private IPs** - `100.x.x.x` range not exposed to internet
- **Tailscale DNS** - Use hostnames instead of IPs
- **Access Control** - Define who can access dispatcher
- **Audit Trail** - Tailscale logs all connections

---

## What You'll See

When fully deployed on your Tailnet:

```
tailscale status

100.64.0.1     punk@MacBook-Pro.tail9876aa.ts.net
100.65.0.2     packetfs-dispatcher.tail9876aa.ts.net
100.65.0.3     packetfs-compute-1.tail9876aa.ts.net
100.65.0.4     packetfs-compute-2.tail9876aa.ts.net
100.65.0.5     packetfs-compute-3.tail9876aa.ts.net
100.65.0.6     packetfs-compute-4.tail9876aa.ts.net
100.65.0.7     packetfs-compute-5.tail9876aa.ts.net
...

All connected via WireGuard encryption
All can reach dispatcher at packetfs-dispatcher:8080
All can reach Redis at packetfs-redis:6379
```

---

## Next: Go Live

1. [ ] Generate Tailscale auth key
2. [ ] Start dispatcher locally
3. [ ] Launch 3-5 EC2 compute nodes
4. [ ] Deploy browser nodes
5. [ ] Submit jobs
6. [ ] Watch them execute
7. [ ] Scale to 100+ nodes
8. [ ] Dominate your Tailnet 🚀

Let's get those nodes online!
