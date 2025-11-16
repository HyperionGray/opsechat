#!/usr/bin/env python3
"""
End-to-end test: Route a PacketFS job through all substrates
Demonstrates: Cloudflare → Lambda → Fly.io → Browser
"""

import asyncio
import json
from dispatcher import (
    ComputeDispatcher, 
    ComputeJob,
    SubstrateType
)

# Test data: a PacketFS program
TEST_PROGRAM = {
    'op': 'counteq',
    'data_url': 'https://example.com/test-data.bin',
    'imm': 42,
    'offset': 0,
    'length': 1024 * 1024  # 1MB
}


async def test_single_job():
    """Test: submit and execute a single job"""
    print("\n" + "="*60)
    print("TEST 1: Single Job Execution")
    print("="*60)
    
    dispatcher = ComputeDispatcher()
    await dispatcher.initialize()
    
    # Create job
    job = ComputeJob(
        program=TEST_PROGRAM,
        required_memory_mb=512,
        required_duration_seconds=30
    )
    
    print(f"\nJob ID: {job.job_id}")
    print(f"Program: {job.program['op']}")
    print(f"Memory: {job.required_memory_mb}MB")
    
    # Submit
    job_id = await dispatcher.submit_job(job)
    print(f"Status: Submitted")
    
    # Dispatch (in real scenario, this runs continuously)
    result = await dispatcher.dispatch_job(job)
    
    print(f"\nResult:")
    print(f"  Substrate: {result.substrate_type.value}")
    print(f"  Success: {result.success}")
    print(f"  Execution Time: {result.execution_time_ms:.1f}ms")
    print(f"  Cost: ${result.cost_usd:.4f}")
    
    if result.error:
        print(f"  Error: {result.error}")
    
    await dispatcher.shutdown()
    return result.success


async def test_substrate_selection():
    """Test: verify substrate selection logic"""
    print("\n" + "="*60)
    print("TEST 2: Substrate Selection Logic")
    print("="*60)
    
    dispatcher = ComputeDispatcher()
    await dispatcher.initialize()
    
    # Test different job profiles
    test_cases = [
        {
            'name': 'Small, latency-sensitive',
            'job': ComputeJob(
                program={'op': 'counteq', 'data_url': 'https://example.com/data'},
                required_memory_mb=128,
                required_duration_seconds=5
            ),
            'expected': 'browser_wasm'  # Cheapest, low latency
        },
        {
            'name': 'Medium, state-dependent',
            'job': ComputeJob(
                program={'op': 'fnv64', 'data_url': 'https://example.com/data'},
                required_memory_mb=256,
                required_duration_seconds=15
            ),
            'expected': 'cloudflare_worker'  # Has state via Durable Objects
        },
        {
            'name': 'Large compute',
            'job': ComputeJob(
                program={'op': 'crc32c', 'data_url': 'https://example.com/data'},
                required_memory_mb=1024,
                required_duration_seconds=60
            ),
            'expected': 'aws_lambda'  # More memory available
        }
    ]
    
    for tc in test_cases:
        adapter = await dispatcher.select_substrate(tc['job'])
        
        if adapter:
            actual = adapter.substrate_type.value
            expected = tc['expected']
            match = "✓" if expected in actual else "✗"
            
            print(f"\n{match} {tc['name']}")
            print(f"  Expected: {expected}")
            print(f"  Actual: {actual}")
            print(f"  Capability: {adapter.capability.to_dict()}")
        else:
            print(f"\n✗ {tc['name']} - No suitable substrate")
    
    await dispatcher.shutdown()


async def test_metrics_collection():
    """Test: verify metrics are collected"""
    print("\n" + "="*60)
    print("TEST 3: Metrics Collection")
    print("="*60)
    
    dispatcher = ComputeDispatcher()
    await dispatcher.initialize()
    
    # Submit multiple jobs
    jobs = [
        ComputeJob(program={'op': 'counteq', 'data_url': f'https://example.com/data{i}'})
        for i in range(3)
    ]
    
    for job in jobs:
        await dispatcher.submit_job(job)
    
    # Process some jobs (they'll fail in test, but metrics still recorded)
    for job in jobs[:2]:
        result = await dispatcher.dispatch_job(job)
        await dispatcher._record_metric(result)
    
    # Get metrics
    metrics = await dispatcher.get_metrics(limit=10)
    
    print(f"\nMetrics recorded: {len(metrics)}")
    for i, m in enumerate(metrics[:3]):
        print(f"\n  [{i+1}] {m['timestamp']}")
        print(f"      Substrate: {m['substrate']}")
        print(f"      Success: {m['success']}")
        print(f"      Time: {m['exec_time_ms']:.1f}ms")
        print(f"      Cost: ${m['cost_usd']:.4f}")
    
    await dispatcher.shutdown()


async def test_parallel_dispatch():
    """Test: dispatch multiple jobs in parallel"""
    print("\n" + "="*60)
    print("TEST 4: Parallel Job Dispatch")
    print("="*60)
    
    dispatcher = ComputeDispatcher()
    await dispatcher.initialize()
    
    # Create multiple jobs
    num_jobs = 5
    jobs = [
        ComputeJob(
            program={'op': 'fnv64', 'data_url': f'https://example.com/data{i}'},
            required_memory_mb=256 + (i * 64)
        )
        for i in range(num_jobs)
    ]
    
    print(f"\nSubmitting {num_jobs} jobs in parallel...")
    
    # Submit all jobs
    job_ids = []
    for job in jobs:
        job_id = await dispatcher.submit_job(job)
        job_ids.append(job_id)
    
    print(f"✓ Submitted {len(job_ids)} jobs")
    
    # Dispatch all in parallel
    results = await asyncio.gather(
        *[dispatcher.dispatch_job(job) for job in jobs],
        return_exceptions=True
    )
    
    success_count = sum(1 for r in results if isinstance(r, object) and r.success)
    print(f"✓ Completed {success_count}/{num_jobs} jobs")
    
    # Show distribution
    substrate_counts = {}
    for r in results:
        if hasattr(r, 'substrate_type'):
            substrate = r.substrate_type.value
            substrate_counts[substrate] = substrate_counts.get(substrate, 0) + 1
    
    print(f"\nSubstrate distribution:")
    for substrate, count in substrate_counts.items():
        print(f"  {substrate}: {count}")
    
    await dispatcher.shutdown()


async def test_cost_optimization():
    """Test: verify cost-optimal substrate selection"""
    print("\n" + "="*60)
    print("TEST 5: Cost Optimization")
    print("="*60)
    
    dispatcher = ComputeDispatcher()
    await dispatcher.initialize()
    
    # Small job that fits everywhere
    job = ComputeJob(
        program={'op': 'counteq', 'data_url': 'https://example.com/data'},
        required_memory_mb=128,
        required_duration_seconds=5
    )
    
    print(f"\nSmall job (128MB, 5s)")
    print(f"Available substrates and costs:")
    
    # Check all substrates
    for substrate_type, adapter in dispatcher.adapters.items():
        if await adapter.health_check():
            cap = adapter.capability
            score = (cap.cost_per_hour_usd * 100) + cap.latency_ms
            print(f"  {substrate_type.value:20} - ${cap.cost_per_hour_usd:6.2f}/hr, {cap.latency_ms:3.0f}ms latency → score: {score:.1f}")
    
    # Select best
    selected = await dispatcher.select_substrate(job)
    if selected:
        print(f"\n✓ Selected: {selected.substrate_type.value} (lowest cost)")
    
    await dispatcher.shutdown()


async def main():
    """Run all tests"""
    print("\n" + "█"*60)
    print("█ PacketFS Unified Compute - Dispatcher Tests")
    print("█"*60)
    
    try:
        # Test 1: Single job
        await test_single_job()
        
        # Test 2: Substrate selection
        await test_substrate_selection()
        
        # Test 3: Metrics
        await test_metrics_collection()
        
        # Test 4: Parallel dispatch
        await test_parallel_dispatch()
        
        # Test 5: Cost optimization
        await test_cost_optimization()
        
        print("\n" + "█"*60)
        print("█ All tests completed!")
        print("█"*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
