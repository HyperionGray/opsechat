#!/usr/bin/env python3
"""
PacketFS Unified Compute Dispatcher
Routes PacketFS jobs to optimal substrates: Cloudflare, Lambda, Fly.io, Browser, Unikernels
"""

import asyncio
import json
import redis.asyncio as redis
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
import uuid
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SubstrateType(Enum):
    """Available compute substrates"""
    CLOUDFLARE_WORKER = "cloudflare_worker"
    CLOUDFLARE_DURABLE_OBJECT = "cloudflare_do"
    AWS_LAMBDA = "aws_lambda"
    AWS_SPOT = "aws_spot"
    FLY_IO = "fly_io"
    BROWSER_WASM = "browser_wasm"
    BROWSER_WORKER = "browser_worker"
    UNIKERNEL_SWARM = "unikernel_swarm"


@dataclass
class SubstrateCapability:
    """Define what a substrate can do"""
    substrate_type: SubstrateType
    max_concurrent_jobs: int
    max_memory_mb: int
    max_duration_seconds: int
    supports_gpu: bool
    supports_persistent_state: bool
    cost_per_hour_usd: float
    latency_ms: float
    available_slots: int = 0
    
    def to_dict(self):
        return {
            'type': self.substrate_type.value,
            'max_concurrent': self.max_concurrent_jobs,
            'max_memory_mb': self.max_memory_mb,
            'max_duration_s': self.max_duration_seconds,
            'gpu': self.supports_gpu,
            'persistent_state': self.supports_persistent_state,
            'cost_usd_hour': self.cost_per_hour_usd,
            'latency_ms': self.latency_ms,
            'available_slots': self.available_slots
        }


@dataclass
class ComputeJob:
    """A job to be executed"""
    job_id: str
    program: Dict  # PacketFS program (with ops, data references, etc)
    required_memory_mb: int = 256
    required_duration_seconds: int = 30
    requires_gpu: bool = False
    priority: int = 0  # Higher = more important
    timeout_seconds: int = 300
    created_at: str = None
    metadata: Dict = None
    
    def __post_init__(self):
        if not self.job_id:
            self.job_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.metadata:
            self.metadata = {}
    
    def to_dict(self):
        return {
            'job_id': self.job_id,
            'program': self.program,
            'required_memory_mb': self.required_memory_mb,
            'required_duration_s': self.required_duration_seconds,
            'requires_gpu': self.requires_gpu,
            'priority': self.priority,
            'timeout_s': self.timeout_seconds,
            'created_at': self.created_at,
            'metadata': self.metadata
        }


@dataclass
class JobResult:
    """Result from executed job"""
    job_id: str
    substrate_type: SubstrateType
    success: bool
    result_data: Dict
    execution_time_ms: float
    bytes_processed: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None
    completed_at: str = None
    
    def __post_init__(self):
        if not self.completed_at:
            self.completed_at = datetime.utcnow().isoformat()
    
    def to_dict(self):
        return {
            'job_id': self.job_id,
            'substrate': self.substrate_type.value,
            'success': self.success,
            'result': self.result_data,
            'exec_time_ms': self.execution_time_ms,
            'bytes_processed': self.bytes_processed,
            'cost_usd': self.cost_usd,
            'error': self.error,
            'completed_at': self.completed_at
        }


class SubstrateAdapter(ABC):
    """Abstract base for substrate adapters"""
    
    def __init__(self, substrate_type: SubstrateType):
        self.substrate_type = substrate_type
        self.capability = self._get_capability()
    
    @abstractmethod
    async def execute(self, job: ComputeJob) -> JobResult:
        """Execute a job on this substrate"""
        pass
    
    @abstractmethod
    def _get_capability(self) -> SubstrateCapability:
        """Return substrate capabilities"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if substrate is available"""
        pass


class CloudflareAdapter(SubstrateAdapter):
    """Cloudflare Workers substrate"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.worker_url = "https://packetfs-compute.example.com/compute"
        super().__init__(SubstrateType.CLOUDFLARE_WORKER)
    
    def _get_capability(self) -> SubstrateCapability:
        return SubstrateCapability(
            substrate_type=SubstrateType.CLOUDFLARE_WORKER,
            max_concurrent_jobs=10000,
            max_memory_mb=128,
            max_duration_seconds=30,  # CF timeout
            supports_gpu=False,
            supports_persistent_state=True,  # via Durable Objects
            cost_per_hour_usd=0.50,  # Free tier + small paid
            latency_ms=50,
            available_slots=10000
        )
    
    async def execute(self, job: ComputeJob) -> JobResult:
        """Execute via Cloudflare Worker"""
        import aiohttp
        import time
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    'job_id': job.job_id,
                    'program': job.program,
                    'timeout_s': job.timeout_seconds
                }
                
                async with session.post(
                    self.worker_url,
                    json=payload,
                    headers={'Authorization': f'Bearer {self.api_token}'},
                    timeout=aiohttp.ClientTimeout(total=job.timeout_seconds + 10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        execution_time_ms = (time.time() - start_time) * 1000
                        
                        return JobResult(
                            job_id=job.job_id,
                            substrate_type=self.substrate_type,
                            success=True,
                            result_data=data.get('results', {}),
                            execution_time_ms=execution_time_ms,
                            bytes_processed=data.get('bytes_processed', 0),
                            cost_usd=data.get('cost_usd', 0.0001)
                        )
                    else:
                        error = await resp.text()
                        return JobResult(
                            job_id=job.job_id,
                            substrate_type=self.substrate_type,
                            success=False,
                            result_data={},
                            execution_time_ms=(time.time() - start_time) * 1000,
                            error=f"HTTP {resp.status}: {error}"
                        )
        except Exception as e:
            return JobResult(
                job_id=job.job_id,
                substrate_type=self.substrate_type,
                success=False,
                result_data={},
                execution_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def health_check(self) -> bool:
        """Check Cloudflare availability"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.worker_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except:
            return False


class LambdaAdapter(SubstrateAdapter):
    """AWS Lambda substrate"""
    
    def __init__(self, aws_region: str = "us-east-1"):
        self.region = aws_region
        self.function_name = "packetfs-compute"
        super().__init__(SubstrateType.AWS_LAMBDA)
    
    def _get_capability(self) -> SubstrateCapability:
        return SubstrateCapability(
            substrate_type=SubstrateType.AWS_LAMBDA,
            max_concurrent_jobs=1000,
            max_memory_mb=10240,
            max_duration_seconds=900,  # 15 min timeout
            supports_gpu=False,  # Via Lambda@Edge only
            supports_persistent_state=False,
            cost_per_hour_usd=0.50,  # Variable, ~$0.0000002 per execution
            latency_ms=100,
            available_slots=100  # Conservative estimate
        )
    
    async def execute(self, job: ComputeJob) -> JobResult:
        """Execute via AWS Lambda"""
        try:
            import boto3
            import time
            
            start_time = time.time()
            client = boto3.client('lambda', region_name=self.region)
            
            payload = {
                'job_id': job.job_id,
                'program': job.program,
                'timeout_s': min(job.timeout_seconds, 900)
            }
            
            response = client.invoke(
                FunctionName=self.function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            if response['StatusCode'] == 200:
                result_payload = json.loads(response['Payload'].read())
                return JobResult(
                    job_id=job.job_id,
                    substrate_type=self.substrate_type,
                    success=True,
                    result_data=result_payload.get('results', {}),
                    execution_time_ms=execution_time_ms,
                    bytes_processed=result_payload.get('bytes_processed', 0),
                    cost_usd=0.0002  # Rough estimate
                )
            else:
                return JobResult(
                    job_id=job.job_id,
                    substrate_type=self.substrate_type,
                    success=False,
                    result_data={},
                    execution_time_ms=execution_time_ms,
                    error=f"Lambda returned {response['StatusCode']}"
                )
        except Exception as e:
            return JobResult(
                job_id=job.job_id,
                substrate_type=self.substrate_type,
                success=False,
                result_data={},
                execution_time_ms=0,
                error=str(e)
            )
    
    async def health_check(self) -> bool:
        """Check Lambda availability"""
        try:
            import boto3
            client = boto3.client('lambda', region_name=self.region)
            client.get_function(FunctionName=self.function_name)
            return True
        except:
            return False


class FlyIOAdapter(SubstrateAdapter):
    """Fly.io VM substrate"""
    
    def __init__(self, api_token: str, app_name: str = "packetfs-compute"):
        self.api_token = api_token
        self.app_name = app_name
        self.api_url = "https://api.fly.io/graphql"
        super().__init__(SubstrateType.FLY_IO)
    
    def _get_capability(self) -> SubstrateCapability:
        return SubstrateCapability(
            substrate_type=SubstrateType.FLY_IO,
            max_concurrent_jobs=500,
            max_memory_mb=2048,
            max_duration_seconds=3600,  # 1 hour
            supports_gpu=False,
            supports_persistent_state=True,  # Via volumes
            cost_per_hour_usd=1.50,  # Shared VM starting price
            latency_ms=150,
            available_slots=50
        )
    
    async def execute(self, job: ComputeJob) -> JobResult:
        """Execute via Fly.io"""
        import aiohttp
        import time
        
        start_time = time.time()
        try:
            # Query Fly.io API to spawn/scale VM
            query = """
            mutation {
              scaleVMCount(input: {appId: "%s", processGroup: "compute", count: 1}) {
                app { id }
              }
            }
            """ % self.app_name
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={'query': query},
                    headers={'Authorization': f'Bearer {self.api_token}'},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        # VM scaled, send job
                        job_url = f"https://{self.app_name}.fly.dev/compute"
                        async with session.post(
                            job_url,
                            json=job.to_dict(),
                            timeout=aiohttp.ClientTimeout(total=job.timeout_seconds + 10)
                        ) as job_resp:
                            if job_resp.status == 200:
                                data = await job_resp.json()
                                execution_time_ms = (time.time() - start_time) * 1000
                                
                                return JobResult(
                                    job_id=job.job_id,
                                    substrate_type=self.substrate_type,
                                    success=True,
                                    result_data=data.get('results', {}),
                                    execution_time_ms=execution_time_ms,
                                    cost_usd=0.001  # Rough estimate per job
                                )
        except Exception as e:
            pass
        
        return JobResult(
            job_id=job.job_id,
            substrate_type=self.substrate_type,
            success=False,
            result_data={},
            execution_time_ms=(time.time() - start_time) * 1000,
            error="Fly.io execution failed"
        )
    
    async def health_check(self) -> bool:
        """Check Fly.io app availability"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://{self.app_name}.fly.dev/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except:
            return False


class BrowserAdapter(SubstrateAdapter):
    """Browser-based execution (Wasm + Service Worker)"""
    
    def __init__(self, service_worker_url: str):
        self.service_worker_url = service_worker_url
        super().__init__(SubstrateType.BROWSER_WASM)
    
    def _get_capability(self) -> SubstrateCapability:
        return SubstrateCapability(
            substrate_type=SubstrateType.BROWSER_WASM,
            max_concurrent_jobs=100000,  # Huge scale via many browsers
            max_memory_mb=512,
            max_duration_seconds=60,
            supports_gpu=True,  # WebGL
            supports_persistent_state=False,
            cost_per_hour_usd=0.0,  # FREE!
            latency_ms=200,
            available_slots=100000
        )
    
    async def execute(self, job: ComputeJob) -> JobResult:
        """Execute via browser Service Worker"""
        import aiohttp
        import time
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    'type': 'execute',
                    'job_id': job.job_id,
                    'program': job.program
                }
                
                async with session.post(
                    self.service_worker_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=job.timeout_seconds + 10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        execution_time_ms = (time.time() - start_time) * 1000
                        
                        return JobResult(
                            job_id=job.job_id,
                            substrate_type=self.substrate_type,
                            success=True,
                            result_data=data.get('results', {}),
                            execution_time_ms=execution_time_ms,
                            cost_usd=0.0  # FREE
                        )
        except Exception as e:
            pass
        
        return JobResult(
            job_id=job.job_id,
            substrate_type=self.substrate_type,
            success=False,
            result_data={},
            execution_time_ms=(time.time() - start_time) * 1000,
            error="Browser execution failed"
        )
    
    async def health_check(self) -> bool:
        """Check browser service worker availability"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.service_worker_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except:
            return False


class ComputeDispatcher:
    """Main dispatcher that routes jobs to optimal substrates"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.adapters: Dict[SubstrateType, SubstrateAdapter] = {}
        self.job_queue_key = "packetfs:jobs:queue"
        self.result_key_prefix = "packetfs:results:"
        self.metrics_key = "packetfs:metrics"
    
    async def initialize(self):
        """Initialize dispatcher and adapters"""
        self.redis = await redis.from_url(self.redis_url)
        
        # Register adapters
        self.adapters[SubstrateType.CLOUDFLARE_WORKER] = CloudflareAdapter(
            api_token=self._get_env('CLOUDFLARE_API_TOKEN')
        )
        self.adapters[SubstrateType.AWS_LAMBDA] = LambdaAdapter()
        self.adapters[SubstrateType.FLY_IO] = FlyIOAdapter(
            api_token=self._get_env('FLY_API_TOKEN')
        )
        self.adapters[SubstrateType.BROWSER_WASM] = BrowserAdapter(
            service_worker_url=self._get_env('SERVICE_WORKER_URL', 'http://localhost:3000')
        )
        
        logger.info(f"Dispatcher initialized with {len(self.adapters)} substrates")
    
    def _get_env(self, key: str, default: str = None) -> str:
        """Get environment variable"""
        import os
        return os.getenv(key, default)
    
    async def submit_job(self, job: ComputeJob) -> str:
        """Submit a job to the queue"""
        job_data = json.dumps(job.to_dict())
        await self.redis.lpush(self.job_queue_key, job_data)
        logger.info(f"Job {job.job_id} submitted")
        return job.job_id
    
    async def select_substrate(self, job: ComputeJob) -> Optional[SubstrateAdapter]:
        """Select best substrate for a job"""
        # Scoring logic: prefer fast, cheap, available
        candidates = []
        
        for substrate_type, adapter in self.adapters.items():
            if not await adapter.health_check():
                continue
            
            cap = adapter.capability
            
            # Check if job fits
            if (job.required_memory_mb > cap.max_memory_mb or
                job.required_duration_seconds > cap.max_duration_seconds or
                (job.requires_gpu and not cap.supports_gpu)):
                continue
            
            # Score: lower is better
            # Cost + latency, normalized
            score = (cap.cost_per_hour_usd * 100) + cap.latency_ms
            
            candidates.append((score, adapter))
        
        if not candidates:
            return None
        
        # Return lowest-scoring (best) substrate
        candidates.sort()
        logger.info(f"Selected {candidates[0][1].substrate_type.value} for job {job.job_id}")
        return candidates[0][1]
    
    async def dispatch_job(self, job: ComputeJob) -> JobResult:
        """Dispatch and execute a single job"""
        adapter = await self.select_substrate(job)
        
        if not adapter:
            logger.error(f"No suitable substrate for job {job.job_id}")
            return JobResult(
                job_id=job.job_id,
                substrate_type=SubstrateType.CLOUDFLARE_WORKER,
                success=False,
                result_data={},
                execution_time_ms=0,
                error="No suitable substrate available"
            )
        
        result = await adapter.execute(job)
        
        # Store result in Redis
        result_key = f"{self.result_key_prefix}{job.job_id}"
        await self.redis.setex(
            result_key,
            86400,  # 24 hour TTL
            json.dumps(result.to_dict())
        )
        
        # Update metrics
        await self._record_metric(result)
        
        logger.info(f"Job {job.job_id} completed on {result.substrate_type.value}: "
                   f"success={result.success}, time={result.execution_time_ms}ms, "
                   f"cost=${result.cost_usd:.4f}")
        
        return result
    
    async def _record_metric(self, result: JobResult):
        """Record execution metric"""
        metric = {
            'timestamp': datetime.utcnow().isoformat(),
            'job_id': result.job_id,
            'substrate': result.substrate_type.value,
            'success': result.success,
            'exec_time_ms': result.execution_time_ms,
            'cost_usd': result.cost_usd
        }
        await self.redis.lpush(self.metrics_key, json.dumps(metric))
    
    async def process_queue(self):
        """Continuously process job queue"""
        logger.info("Starting job queue processor")
        
        while True:
            try:
                # Get next job from queue
                job_data = await self.redis.rpop(self.job_queue_key)
                
                if not job_data:
                    await asyncio.sleep(0.1)
                    continue
                
                job_dict = json.loads(job_data)
                job = ComputeJob(**job_dict)
                
                # Dispatch job
                result = await self.dispatch_job(job)
                
                # Small delay to avoid hammering
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                await asyncio.sleep(1)
    
    async def get_result(self, job_id: str) -> Optional[JobResult]:
        """Retrieve job result"""
        result_key = f"{self.result_key_prefix}{job_id}"
        result_data = await self.redis.get(result_key)
        
        if not result_data:
            return None
        
        result_dict = json.loads(result_data)
        result_dict['substrate_type'] = SubstrateType(result_dict['substrate'])
        return JobResult(**result_dict)
    
    async def get_metrics(self, limit: int = 100) -> List[Dict]:
        """Get recent execution metrics"""
        metrics_data = await self.redis.lrange(self.metrics_key, 0, limit - 1)
        return [json.loads(m) for m in metrics_data]
    
    async def shutdown(self):
        """Cleanup"""
        if self.redis:
            await self.redis.close()


async def main():
    """Demo: dispatch jobs through multiple substrates"""
    dispatcher = ComputeDispatcher()
    await dispatcher.initialize()
    
    # Create some test jobs
    jobs = [
        ComputeJob(
            program={'op': 'counteq', 'data_url': 'https://example.com/data', 'imm': 42},
            required_memory_mb=128,
            required_duration_seconds=10
        ),
        ComputeJob(
            program={'op': 'crc32c', 'data_url': 'https://example.com/data'},
            required_memory_mb=256,
            required_duration_seconds=5
        ),
        ComputeJob(
            program={'op': 'fnv64', 'data_url': 'https://example.com/data'},
            required_memory_mb=512,
            required_duration_seconds=15
        ),
    ]
    
    # Submit jobs
    job_ids = []
    for job in jobs:
        job_id = await dispatcher.submit_job(job)
        job_ids.append(job_id)
    
    # Process queue in background
    processor_task = asyncio.create_task(dispatcher.process_queue())
    
    # Wait for jobs to complete
    await asyncio.sleep(5)
    
    # Retrieve results
    print("\n=== Job Results ===")
    for job_id in job_ids:
        result = await dispatcher.get_result(job_id)
        if result:
            print(f"Job {job_id}: {result.substrate_type.value}, "
                  f"success={result.success}, time={result.execution_time_ms}ms, "
                  f"cost=${result.cost_usd:.4f}")
    
    # Show metrics
    print("\n=== Metrics ===")
    metrics = await dispatcher.get_metrics()
    for metric in metrics[:5]:
        print(metric)
    
    # Cleanup
    processor_task.cancel()
    await dispatcher.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
