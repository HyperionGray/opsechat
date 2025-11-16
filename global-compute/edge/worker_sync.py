#!/usr/bin/env python3
"""
Edge Worker Sync - Coordinate PacketFS Lab containers with Cloudflare Workers

This script runs inside PacketFS Lab containers and:
1. Polls Cloudflare Workers for pCPU jobs
2. Executes jobs using local pCPU agent
3. Reports results back to the worker
4. Maintains heartbeat with edge network
"""

import os
import sys
import json
import time
import requests
import subprocess
from datetime import datetime
from pathlib import Path

# Configuration from environment
WORKER_URL = os.getenv('GENESIS_WORKER_URL', 'https://genesis-worker-v2.scaryjerrynorthwest69.workers.dev')
REGISTRY_URL = os.getenv('GENESIS_REGISTRY_URL', 'https://punk-ripper.lungfish-sirius.ts.net')
VM_ID = os.getenv('VM_ID', 'unknown')
POLL_INTERVAL = int(os.getenv('EDGE_POLL_INTERVAL', '30'))  # seconds

# Local paths
PCPU_AGENT = Path('/opt/packetfs/scripts/pcpu/pfs_pcpu_agent.py')
PCPU_EXEC = Path('/opt/packetfs/scripts/pcpu/pcpu_exec.py')
LOG_DIR = Path('/opt/packetfs/logs/edge')
LOG_DIR.mkdir(parents=True, exist_ok=True)

def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().isoformat()
    msg = f"[{timestamp}] {message}"
    print(msg)
    
    # Also write to log file
    log_file = LOG_DIR / 'worker_sync.log'
    with open(log_file, 'a') as f:
        f.write(msg + '\n')

def get_vm_id():
    """Get or generate VM ID"""
    global VM_ID
    
    if VM_ID != 'unknown':
        return VM_ID
    
    # Try to read from file
    vm_id_file = Path('/etc/pfs-vm-id')
    if vm_id_file.exists():
        VM_ID = vm_id_file.read_text().strip()
        return VM_ID
    
    # Generate new ID
    import hashlib
    hostname = os.uname().nodename
    VM_ID = hashlib.sha256(f"{hostname}-{time.time()}".encode()).hexdigest()[:16]
    vm_id_file.write_text(VM_ID)
    
    return VM_ID

def poll_for_jobs():
    """Poll Cloudflare Worker for pending pCPU jobs"""
    try:
        response = requests.get(
            f"{WORKER_URL}/pcpu/jobs/pending",
            params={'vm_id': get_vm_id()},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('jobs', [])
        elif response.status_code == 404:
            # No endpoint yet, that's okay
            return []
        else:
            log(f"⚠️  Failed to poll for jobs: HTTP {response.status_code}")
            return []
            
    except requests.exceptions.RequestException as e:
        log(f"⚠️  Error polling for jobs: {e}")
        return []

def execute_job(job):
    """Execute a pCPU job locally"""
    job_id = job.get('job_id', 'unknown')
    log(f"📋 Executing job {job_id}")
    
    try:
        # Job format:
        # {
        #   "job_id": "uuid",
        #   "op": "xor"|"add"|"fnv"|"crc32c"|"counteq",
        #   "data": "base64_encoded_data",
        #   "imm": 255  # for xor/add
        # }
        
        op = job.get('op', 'xor')
        data = job.get('data', '')
        imm = job.get('imm', 0)
        
        # Create temp job file
        job_file = LOG_DIR / f"job_{job_id}.json"
        with open(job_file, 'w') as f:
            json.dump(job, f)
        
        # Execute via pCPU agent
        result = subprocess.run(
            [sys.executable, str(PCPU_EXEC), '--job', str(job_file)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Parse result
            output = result.stdout.strip()
            log(f"✅ Job {job_id} completed: {output[:100]}")
            
            return {
                'job_id': job_id,
                'status': 'completed',
                'result': output,
                'vm_id': get_vm_id(),
                'completed_at': datetime.now().isoformat()
            }
        else:
            log(f"❌ Job {job_id} failed: {result.stderr}")
            return {
                'job_id': job_id,
                'status': 'failed',
                'error': result.stderr,
                'vm_id': get_vm_id()
            }
            
    except subprocess.TimeoutExpired:
        log(f"⏰ Job {job_id} timed out")
        return {
            'job_id': job_id,
            'status': 'timeout',
            'vm_id': get_vm_id()
        }
    except Exception as e:
        log(f"💥 Job {job_id} error: {e}")
        return {
            'job_id': job_id,
            'status': 'error',
            'error': str(e),
            'vm_id': get_vm_id()
        }

def report_result(result):
    """Report job result back to worker"""
    try:
        response = requests.post(
            f"{WORKER_URL}/pcpu/results",
            json=result,
            timeout=10
        )
        
        if response.status_code == 200:
            log(f"📤 Reported result for job {result['job_id']}")
            return True
        else:
            log(f"⚠️  Failed to report result: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        log(f"⚠️  Error reporting result: {e}")
        return False

def send_heartbeat():
    """Send heartbeat to both worker and registry"""
    vm_id = get_vm_id()
    
    # Get system stats
    try:
        with open('/proc/cpuinfo') as f:
            cpu_count = len([line for line in f if line.startswith('processor')])
    except:
        cpu_count = 1
    
    heartbeat_data = {
        'vm_id': vm_id,
        'pcpu_cores': cpu_count,
        'timestamp': datetime.now().isoformat(),
        'worker_sync': True
    }
    
    # Send to Genesis Registry
    try:
        requests.post(
            f"{REGISTRY_URL}/api/vm/heartbeat",
            json=heartbeat_data,
            timeout=5
        )
    except:
        pass  # Non-critical
    
    log(f"💓 Heartbeat sent (VM: {vm_id}, cores: {cpu_count})")

def main():
    """Main sync loop"""
    log("🌊🔥💀 Edge Worker Sync Starting 💀🔥🌊")
    log(f"Worker URL: {WORKER_URL}")
    log(f"Registry URL: {REGISTRY_URL}")
    log(f"VM ID: {get_vm_id()}")
    log(f"Poll interval: {POLL_INTERVAL}s")
    
    iteration = 0
    while True:
        try:
            iteration += 1
            
            # Poll for jobs
            jobs = poll_for_jobs()
            if jobs:
                log(f"📥 Found {len(jobs)} pending jobs")
                
                for job in jobs:
                    result = execute_job(job)
                    report_result(result)
            
            # Send heartbeat every 10 iterations
            if iteration % 10 == 0:
                send_heartbeat()
            
            # Sleep
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            log("⚠️  Interrupted by user")
            break
        except Exception as e:
            log(f"💥 Error in main loop: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()
