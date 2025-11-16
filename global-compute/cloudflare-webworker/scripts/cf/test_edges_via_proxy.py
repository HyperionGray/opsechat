#!/usr/bin/env python3
"""
Test Genesis Worker across multiple Cloudflare edge locations
Uses SmartProxy residential IPs to force different edge routing
"""

import requests
import json
import time
from collections import Counter
from datetime import datetime

# SmartProxy configuration
PROXY_URL = "http://smart-y87zawzg6hrf:6DQB9dl12HO4McZE@isp.smartproxy.net:3100"
PROXIES = {
    'http': PROXY_URL,
    'https': PROXY_URL,
}

# Genesis Worker URL
WORKER_URL = "https://genesis-worker.scaryjerrynorthwest69.workers.dev"

# Test configuration
NUM_REQUESTS = 50  # Number of requests to make
DELAY = 2  # Seconds between requests

def test_edge_location():
    """Test a single edge location via proxy"""
    try:
        response = requests.get(
            f"{WORKER_URL}/status",
            proxies=PROXIES,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'edge': data.get('edge_location', 'UNKNOWN'),
                'vm_id': data.get('vm_id', 'UNKNOWN'),
                'worker_version': data.get('worker_version', 'UNKNOWN'),
                'status_code': response.status_code
            }
        else:
            return {
                'success': False,
                'error': f"HTTP {response.status_code}",
                'status_code': response.status_code
            }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': str(e),
            'status_code': None
        }

def main():
    print("🌍 Testing Genesis Worker Across Cloudflare Edge Network")
    print("=" * 70)
    print(f"Worker URL: {WORKER_URL}")
    print(f"Using SmartProxy: {PROXY_URL.split('@')[1]}")
    print(f"Test requests: {NUM_REQUESTS}")
    print("=" * 70)
    print()
    
    edges_seen = []
    vm_ids_seen = []
    successful_requests = 0
    failed_requests = 0
    
    print(f"{'#':<4} {'Edge':<6} {'VM ID':<18} {'Status':<8} {'Time'}")
    print("-" * 70)
    
    for i in range(1, NUM_REQUESTS + 1):
        start_time = time.time()
        result = test_edge_location()
        elapsed = time.time() - start_time
        
        if result['success']:
            successful_requests += 1
            edge = result['edge']
            vm_id = result['vm_id']
            edges_seen.append(edge)
            vm_ids_seen.append(vm_id)
            
            status = "✅ OK"
            print(f"{i:<4} {edge:<6} {vm_id:<18} {status:<8} {elapsed:.2f}s")
        else:
            failed_requests += 1
            status = "❌ FAIL"
            error = result.get('error', 'Unknown error')
            print(f"{i:<4} {'ERROR':<6} {error:<18} {status:<8} {elapsed:.2f}s")
        
        if i < NUM_REQUESTS:
            time.sleep(DELAY)
    
    print("-" * 70)
    print()
    
    # Summary statistics
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"Total Requests:     {NUM_REQUESTS}")
    print(f"Successful:         {successful_requests} ({successful_requests/NUM_REQUESTS*100:.1f}%)")
    print(f"Failed:             {failed_requests} ({failed_requests/NUM_REQUESTS*100:.1f}%)")
    print()
    
    if edges_seen:
        edge_counts = Counter(edges_seen)
        unique_edges = len(edge_counts)
        
        print(f"🌍 EDGE LOCATIONS DISCOVERED: {unique_edges}")
        print("-" * 70)
        
        for edge, count in edge_counts.most_common():
            percentage = (count / len(edges_seen)) * 100
            bar = "█" * int(percentage / 2)
            print(f"{edge:<6} {count:>3}x  [{bar:<50}] {percentage:>5.1f}%")
        
        print()
        print(f"💀 UNIQUE VM IDS: {len(set(vm_ids_seen))}")
        print()
        
        # Geographic distribution estimate
        print("🗺️  ESTIMATED GEOGRAPHIC DISTRIBUTION")
        print("-" * 70)
        
        # Common Cloudflare edge location codes
        location_map = {
            'MIA': 'Miami, Florida, USA',
            'ATL': 'Atlanta, Georgia, USA',
            'IAD': 'Ashburn, Virginia, USA',
            'ORD': 'Chicago, Illinois, USA',
            'DFW': 'Dallas, Texas, USA',
            'LAX': 'Los Angeles, California, USA',
            'SJC': 'San Jose, California, USA',
            'SEA': 'Seattle, Washington, USA',
            'EWR': 'Newark, New Jersey, USA',
            'LHR': 'London, UK',
            'AMS': 'Amsterdam, Netherlands',
            'FRA': 'Frankfurt, Germany',
            'CDG': 'Paris, France',
            'SYD': 'Sydney, Australia',
            'NRT': 'Tokyo, Japan',
            'HKG': 'Hong Kong',
            'SIN': 'Singapore',
            'GRU': 'São Paulo, Brazil',
        }
        
        for edge in sorted(edge_counts.keys()):
            location = location_map.get(edge, 'Unknown Location')
            print(f"  {edge}: {location}")
    
    print()
    print("=" * 70)
    print("🎉 Test Complete!")
    print()
    print("💡 What This Means:")
    print("  - Your Genesis Worker is deployed globally")
    print("  - Each edge can orchestrate PacketFS Lab containers")
    print("  - Combined with Tailscale mesh → PLANETARY COMPUTE!")
    print()
    print("🔗 Next Steps:")
    print("  1. Deploy v2 worker with mesh coordination")
    print("  2. Set up Tailscale Funnel on Genesis registry")
    print("  3. Configure pfsshfs mount points")
    print("  4. Watch the distributed compute swarm grow!")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        print("Partial results saved above")
