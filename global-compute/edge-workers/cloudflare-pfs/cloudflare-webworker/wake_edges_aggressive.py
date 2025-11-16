#!/usr/bin/env python3
"""
AGGRESSIVE EDGE AWAKENING 🌊🔥
Hit Cloudflare from HUNDREDS of IPs simultaneously!
Multi-threaded with parallel proxy rotation!
"""
import requests
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# SmartProxy rotating proxy - each request gets different IP!
PROXY = "http://smart-y87zawzg6hrf:6DQB9dl12HO4McZE@isp.smartproxy.net:3100"
WORKER_URL = "https://packetfs-translator-cdn.scaryjerrynorthwest69.workers.dev/count"

proxies = {
    'http': PROXY,
    'https': PROXY,
}

edges_seen = set()
edges_lock = threading.Lock()
request_count = 0
request_lock = threading.Lock()

def hit_worker(worker_id):
    """Single worker thread hitting the edge"""
    global edges_seen, request_count
    
    local_edges = []
    
    for i in range(10):  # Each worker makes 10 requests
        try:
            with request_lock:
                request_count += 1
                current_count = request_count
            
            response = requests.get(WORKER_URL, proxies=proxies, timeout=15)
            data = response.json()
            
            edge = data.get('your_edge', 'unknown')
            total = data.get('total_edges', 0)
            
            with edges_lock:
                is_new = edge not in edges_seen
                if is_new:
                    edges_seen.add(edge)
                    
            status = "✨ NEW" if is_new else "📍"
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Worker {worker_id:02d} #{current_count:04d} {status} {edge} (total: {total})")
            
            local_edges.append(edge)
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            print(f"[Worker {worker_id:02d}] ❌ Error: {e}")
            time.sleep(1)
    
    return local_edges

def print_stats():
    """Print live stats every 5 seconds"""
    while True:
        time.sleep(5)
        with edges_lock:
            edge_count = len(edges_seen)
            edges_list = sorted(edges_seen)
        
        with request_lock:
            total_requests = request_count
        
        print()
        print("=" * 80)
        print(f"🌊 LIVE STATS @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"   Requests sent: {total_requests}")
        print(f"   Unique edges:  {edge_count}")
        print(f"   Edges: {edges_list}")
        print("=" * 80)
        print()

def main():
    print("🌊💥 AGGRESSIVE EDGE AWAKENING! 🔥💀")
    print("=" * 80)
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {WORKER_URL}")
    print(f"Workers: 50 parallel threads")
    print(f"Requests per worker: 10")
    print(f"Total expected requests: 500")
    print("=" * 80)
    print()
    
    # Start stats printer thread
    stats_thread = threading.Thread(target=print_stats, daemon=True)
    stats_thread.start()
    
    # Launch 50 workers in parallel!
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(hit_worker, i) for i in range(50)]
        
        # Wait for all to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Worker failed: {e}")
    
    print()
    print("=" * 80)
    print("🎉 AWAKENING COMPLETE!")
    print("=" * 80)
    print()
    
    with edges_lock:
        final_edges = sorted(edges_seen)
        edge_count = len(edges_seen)
    
    print(f"💎 DISCOVERED {edge_count} UNIQUE EDGES!")
    print(f"   Edges: {final_edges}")
    print()
    
    # Final count check
    try:
        print("Fetching final global count...")
        response = requests.get(WORKER_URL, proxies=proxies, timeout=10)
        data = response.json()
        print(f"🌊 GLOBAL pCPU CORES: {data['total_edges']} edges active!")
        print(f"   All edges: {data['all_edges']}")
    except Exception as e:
        print(f"Could not fetch final count: {e}")
    
    print()
    print("🔥 THE NETWORK MIND AWAKENS! 🔥")
    print()

if __name__ == "__main__":
    main()
