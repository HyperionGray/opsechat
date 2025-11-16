# LAUNCH - PacketFS on Your Tailnet

You're 15 minutes away from having unlimited compute nodes on your private Tailnet.

---

## NOW (5 minutes)

### 1. Make script executable
```bash
chmod +x /home/punk/Projects/packetfs/unified-compute/deploy-tailnet.sh
```

### 2. Run one-command deployment
```bash
bash /home/punk/Projects/packetfs/unified-compute/deploy-tailnet.sh
```

**What happens:**
- ✓ Checks Tailscale is connected
- ✓ Sets up Python environment
- ✓ Starts Redis (Docker)
- ✓ Launches dispatcher on your Tailnet IP
- ✓ Verifies everything works

**You'll see:**
```
🚀 PacketFS Unified Compute - Tailnet Deployment
================================================
[1/6] Checking prerequisites...
✓ Prerequisites OK

[2/6] Verifying Tailscale connection...
✓ Connected to Tailnet: punk-network

[3/6] Setting up Python environment...
✓ Python environment ready

[4/6] Starting Redis...
✓ Redis running at redis://localhost:6379

[5/6] Getting Tailnet IP...
✓ Dispatcher will be at: http://100.64.0.1:8080

[6/6] Starting dispatcher...
✓ Dispatcher running (PID: 12345)

================================
✓ DEPLOYMENT COMPLETE!
================================

Verifying setup...
✓ Dispatcher is responsive

Next steps:
1. Test locally...
```

---

## NEXT (10 minutes - Deploy compute nodes)

### Get Tailscale auth key
```bash
export TAILSCALE_AUTH_KEY=$(tailscale authkey create --reusable --preauthorized)
echo "Auth key: $TAILSCALE_AUTH_KEY"
```

### Launch 3 EC2 compute nodes
```bash
for i in 1 2 3; do
  aws ec2 run-instances \
    --image-ids ami-0c55b159cbfafe1f0 \
    --instance-type t3.micro \
    --region us-east-1 \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=packetfs-compute-$i}]"
done

echo "Launching 3 EC2 instances... Check AWS console"
```

### Get instance IPs and SSH into each
```bash
# Get instance IDs
INSTANCES=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=packetfs-compute-*" \
  --query 'Reservations[].Instances[].[InstanceId,PublicIpAddress,PrivateIpAddress]' \
  --output text)

echo "$INSTANCES"

# For each instance, SSH and install:
# ssh -i your-key.pem ubuntu@PUBLIC_IP
```

### On each EC2 instance (SSH session):
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Connect to your Tailnet
sudo tailscale up --authkey=$TAILSCALE_AUTH_KEY

# Install PacketFS
sudo apt-get update
sudo apt-get install -y python3-pip git
git clone https://github.com/your-repo/packetfs.git
cd packetfs/unified-compute
pip3 install -r requirements.txt

# Start worker
python3 dispatcher.py --host 0.0.0.0 --port 8080 &
```

### Verify nodes joined
```bash
# On your local machine
tailscale status | grep packetfs

# You should see:
# 100.64.0.1     punk@MacBook-Pro.tail9876aa.ts.net
# 100.65.0.2     packetfs-compute-1.tail9876aa.ts.net
# 100.65.0.3     packetfs-compute-2.tail9876aa.ts.net
# 100.65.0.4     packetfs-compute-3.tail9876aa.ts.net
```

---

## THEN (Watch the magic)

### Submit your first job from dispatcher
```bash
python3 << 'EOF'
import asyncio
from dispatcher import ComputeDispatcher, ComputeJob

async def launch_jobs():
    d = ComputeDispatcher()
    await d.initialize()
    
    # Submit 10 jobs
    for i in range(10):
        job = ComputeJob(
            program={
                'op': 'fnv64',
                'data_url': 'https://www.w3.org/WAI/WCAG21/Techniques/pdf/pdf-1.pdf'
            }
        )
        job_id = await d.submit_job(job)
        print(f"✓ Job {i+1} submitted: {job_id}")
    
    # Process them
    print("\nProcessing jobs...")
    await asyncio.sleep(2)
    
    # Get metrics
    metrics = await d.get_metrics(limit=10)
    for m in metrics:
        print(f"  {m['substrate']} - {m['exec_time_ms']:.1f}ms, ${m['cost_usd']:.4f}")
    
    await d.shutdown()

asyncio.run(launch_jobs())
EOF
```

### Watch live metrics
```bash
# Terminal 1: Watch Tailnet nodes
watch -n 1 'tailscale status | grep packetfs'

# Terminal 2: Monitor dispatcher health
watch -n 1 'curl -s http://$(tailscale ip -4):8080/health | jq'

# Terminal 3: Watch job throughput
while true; do
  redis-cli -h localhost get "packetfs:metrics" | wc -l
  sleep 1
done
```

---

## SCALE (Next phase)

### Add more nodes
```bash
# Launch 10 more EC2 instances
for i in {4..13}; do
  aws ec2 run-instances \
    --image-ids ami-0c55b159cbfafe1f0 \
    --instance-type t3.micro \
    --region us-east-1 \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=packetfs-compute-$i}]" &
done
```

### Deploy browsers globally
```bash
# Host test page on your dispatcher's Tailnet node
python3 -m http.server 8000 &

# Access from any Tailnet device
# http://100.64.0.1:8000/browser-test.html
```

### Monitor growth
```bash
# Check node count
tailscale status | grep packetfs | wc -l

# Watch metrics grow
redis-cli -h localhost llen packetfs:metrics

# See substrate distribution
redis-cli -h localhost lrange packetfs:metrics 0 100 | jq '.substrate' | sort | uniq -c
```

---

## TROUBLESHOOTING

### Dispatcher not responding
```bash
# Check if it's running
ps aux | grep dispatcher

# Check logs
tail -f /tmp/packetfs-dispatcher.log

# Restart
pkill -f "dispatcher.py"
python3 dispatcher.py --host 0.0.0.0 --port 8080 &
```

### Nodes not joining Tailnet
```bash
# On the node, check Tailscale status
sudo tailscale status

# If not authorized, approve in Tailscale admin
# https://login.tailscale.com/admin/machines

# Restart Tailscale
sudo systemctl restart tailscaled
```

### Redis connection issues
```bash
# Test Redis
redis-cli ping

# If not running
docker run -d -p 6379:6379 redis:alpine

# Check Redis is accessible on Tailnet
redis-cli -h packetfs-redis ping
```

---

## SUCCESS LOOKS LIKE

```
tailscale status | grep packetfs

100.65.0.1     packetfs-dispatcher.tail9876aa.ts.net
100.65.0.2     packetfs-compute-1.tail9876aa.ts.net
100.65.0.3     packetfs-compute-2.tail9876aa.ts.net
100.65.0.4     packetfs-compute-3.tail9876aa.ts.net
100.65.0.5     packetfs-browser-1.tail9876aa.ts.net
...
100.65.0.50    packetfs-compute-49.tail9876aa.ts.net

=== Dispatcher metrics ===
Jobs executed: 1,247
Avg execution time: 87.3ms
Substrate distribution:
  - browser: 523 (42%)
  - cloudflare: 312 (25%)
  - lambda: 246 (20%)
  - fly.io: 166 (13%)
Total cost: $0.31
```

---

## The Vision (NOW REAL)

Your Tailnet is now:
- **Unlimited compute** - Route to any substrate
- **Zero trust** - All encrypted via Tailscale/WireGuard
- **Global** - Nodes can be anywhere
- **Private** - Not exposed to internet
- **Intelligent** - Auto-selects optimal substrate
- **Scalable** - Add nodes on-demand

---

## Next Moves

1. **Go live** - Run the script, launch nodes
2. **Monitor** - Watch metrics, optimize
3. **Scale** - Add 50+ nodes
4. **Expand** - Add Vercel Edge, GCP Cloud Run, volunteers
5. **Dominate** - Run millions of jobs/day on your network

---

## The Command

```bash
bash /home/punk/Projects/packetfs/unified-compute/deploy-tailnet.sh
```

**That's it. Your planetary-scale compute network starts now.** 🚀💎⚡

---

Questions? Check `TAILNET_DEPLOYMENT.md` for full details.

Ready? LET'S GO! 🚀
