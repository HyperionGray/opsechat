# PacketFS Unified Compute
## Planetary-Scale Distributed Computing

Turn the entire internet into your CPU. Route PacketFS jobs to Cloudflare, Lambda, Fly.io, browsers, and beyond.

---

## Architecture

```
Job Dispatcher (Redis pub/sub)
    ↓
    ├─→ Cloudflare Workers (fast edge, $0.50/hr)
    ├─→ AWS Lambda (scalable serverless)
    ├─→ Fly.io VMs (global deployment)
    ├─→ Browser Wasm (FREE compute)
    └─→ Unikernel Swarms (tiny, fast)
```

## Components

### 1. Dispatcher (`dispatcher.py`)

Core routing engine that:
- Accepts PacketFS jobs via Redis
- Scores available substrates (cost + latency)
- Selects optimal substrate
- Executes job
- Collects results and metrics

**Usage:**
```python
from dispatcher import ComputeDispatcher, ComputeJob

dispatcher = ComputeDispatcher()
await dispatcher.initialize()

# Submit a job
job = ComputeJob(
    program={'op': 'counteq', 'data_url': 'https://...', 'imm': 42},
    required_memory_mb=256
)
job_id = await dispatcher.submit_job(job)

# Process queue (runs in background)
await dispatcher.process_queue()

# Get results
result = await dispatcher.get_result(job_id)
print(f"Executed on: {result.substrate_type.value}")
print(f"Time: {result.execution_time_ms}ms, Cost: ${result.cost_usd}")
```

### 2. Browser Runtime (`browser-runtime.js`)

Service Worker + Client-side execution for free compute:

**Features:**
- Service Worker handles job distribution
- Client-side PacketFS operation execution
- Metrics reporting
- WebSocket connection to coordinator
- **Cost: $0.00** (user's device)
- **Scale: Billions of browsers**

**Integration:**
```html
<!-- On your website -->
<script src="https://cdn.packetfs.global/browser-runtime.js"></script>

<script>
  // Initialize browser compute
  const compute = new PacketFSBrowserCompute('/packetfs-sw.js');
  await compute.initialize();
  
  // Submit jobs
  const result = await compute.submitJob({
    op: 'fnv64',
    data_url: 'https://example.com/data'
  });
  
  console.log('Result:', result);
  console.log('Metrics:', compute.getMetrics());
</script>
```

### 3. Substrate Adapters

Each cloud provider gets an adapter:

- **CloudflareAdapter** - Workers + Durable Objects
- **LambdaAdapter** - AWS Lambda containers
- **FlyIOAdapter** - Fly.io global VMs
- **BrowserAdapter** - User browser compute

Adapters report:
- Capabilities (memory, duration, GPU, cost)
- Availability (health checks)
- Execution results and metrics

---

## Deployment

### 1. Redis Backend

```bash
# Start Redis (job queue + results)
docker run -d -p 6379:6379 redis:alpine

# Or use cloud Redis
export REDIS_URL="redis://user:pass@host:6379"
```

### 2. Dispatcher Service

```bash
# Install dependencies
pip install redis aiohttp boto3

# Run dispatcher
python dispatcher.py
```

### 3. Deploy Cloudflare Worker

```bash
cd cloudflare-worker/
wrangler publish
# Sets CLOUDFLARE_API_TOKEN env var
```

### 4. Deploy Lambda Function

```bash
# Package Lambda function (see lambda-handler.py template)
zip function.zip lambda_handler.py
aws lambda create-function \
  --function-name packetfs-compute \
  --runtime python3.9 \
  --handler lambda_handler.handler \
  --zip-file fileb://function.zip
```

### 5. Deploy Fly.io App

```bash
fly launch --name packetfs-compute
fly deploy
export FLY_API_TOKEN=$(fly auth token)
```

### 6. Deploy Browser Runtime

```bash
# Host on CDN
gsutil -m cp browser-runtime.js gs://cdn.packetfs.global/v1/browser-runtime.js

# Include on websites
<script src="https://cdn.packetfs.global/v1/browser-runtime.js"></script>
```

---

## Job Submission

### Via Python

```python
import asyncio
from dispatcher import ComputeDispatcher, ComputeJob

async def main():
    dispatcher = ComputeDispatcher()
    await dispatcher.initialize()
    
    # Create job
    job = ComputeJob(
        program={
            'op': 'crc32c',
            'data_url': 'https://example.com/blob.bin',
            'offset': 0,
            'length': 1024 * 1024  # 1MB
        },
        required_memory_mb=512,
        required_duration_seconds=30
    )
    
    # Submit
    job_id = await dispatcher.submit_job(job)
    print(f"Job submitted: {job_id}")
    
    # Process queue (real dispatcher runs this continuously)
    asyncio.create_task(dispatcher.process_queue())
    
    # Wait for result
    await asyncio.sleep(5)
    result = await dispatcher.get_result(job_id)
    
    if result:
        print(f"Success: {result.success}")
        print(f"Substrate: {result.substrate_type.value}")
        print(f"Time: {result.execution_time_ms:.1f}ms")
        print(f"Cost: ${result.cost_usd:.4f}")
        print(f"Results: {result.result_data}")

asyncio.run(main())
```

### Via Redis CLI

```bash
redis-cli lpush packetfs:jobs:queue '{
  "job_id": "my-job-1",
  "program": {
    "op": "counteq",
    "data_url": "https://example.com/data",
    "imm": 42
  },
  "required_memory_mb": 256,
  "required_duration_seconds": 10
}'

# Check result
redis-cli get "packetfs:results:my-job-1"
```

---

## Substrate Selection

Dispatcher automatically chooses the best substrate:

```
Low latency, small job? → Browser (FREE, <200ms)
Medium job, needs state? → Cloudflare ($0.50/hr, edge)
Large compute? → Lambda ($0.0002/invocation)
Long-running? → Fly.io ($1.50/hr per VM)
```

**Scoring formula:**
```
score = (cost_per_hour * 100) + latency_ms
# Lower score = better substrate
```

Dispatcher also checks:
- Memory requirements
- Duration limits
- GPU support
- State persistence needs

---

## Metrics & Monitoring

Real-time metrics in Redis:

```python
# Get recent execution metrics
dispatcher = ComputeDispatcher()
await dispatcher.initialize()

metrics = await dispatcher.get_metrics(limit=100)

for m in metrics:
    print(f"{m['timestamp']}: {m['substrate']} - {m['exec_time_ms']}ms, ${m['cost_usd']:.4f}")
```

Sample output:
```
2024-10-29T04:45:00: cloudflare_worker - 45.2ms, $0.0001
2024-10-29T04:45:01: browser_wasm - 312.1ms, $0.0000
2024-10-29T04:45:02: aws_lambda - 103.5ms, $0.0002
2024-10-29T04:45:03: fly_io - 285.3ms, $0.0008
```

---

## Cost Optimization

### Browser is FREE (0 infrastructure cost!)
- Deploy to CDN
- Include on websites
- Users' devices = compute
- Scale: billions of nodes

### Cloudflare Workers: $0.50/month free
- 100K requests/day free
- $0.50 per million requests after
- Best for latency-sensitive jobs

### Lambda: 1M requests free
- $0.0000002 per execution
- Bulk compute is cheap
- Cold start ~100ms

### Fly.io: Free tier + cheap
- First 3 shared-cpu-1x 256MB VMs free
- $1.50/month for small VM
- Global deployment

---

## Next Steps

1. **Cloudflare Durable Objects** - Stateful job coordination
2. **Vercel Edge Functions** - Additional edge substrate
3. **GCP Cloud Run** - Container-based scale-out
4. **Residential Volunteers** - Community compute mesh
5. **Spot Instances** - Massive parallelism on budget
6. **Mobile Devices** - Billions of smartphones

---

## The Vision

Every internet-connected device becomes a PacketFS compute node. Router jobs intelligently to:
- Cheapest option (browser)
- Fastest option (edge)
- Most scalable option (cloud)
- Best match (all criteria)

**Result:** Unlimited compute at near-zero cost, distributed globally.

🚀💎⚡
