#!/usr/bin/env python3
"""
🌊🔥💀 ULTRA AGGRESSIVE EDGE AWAKENING 💀🔥🌊

SUSTAINED PRESSURE MODE:
- 100 parallel workers
- Continuous requests until stopped
- Live dashboard with stats
- Exponential edge discovery
- SATURATE THE NETWORK!
"""
import requests
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from collections import defaultdict
import sys

# SmartProxy rotating proxy - each request gets different IP!
PROXY = "http://smart-y87zawzg6hrf:6DQB9dl12HO4McZE@isp.smartproxy.net:3100"
WORKER_URL = "https://packetfs-translator-cdn.scaryjerrynorthwest69.workers.dev/count"

proxies = {
    'http': PROXY,
    'https': PROXY,
}

# Global state
edges_seen = set()
edges_lock = threading.Lock()
request_count = 0
error_count = 0
stats_lock = threading.Lock()
edge_history = []  # Track when each edge was discovered
running = True

# Edge discovery rate tracking
edge_times = {}  # edge -> discovery time

def hit_worker_continuous(worker_id):
    """Continuous worker hitting edges until stopped"""
    global edges_seen, request_count, error_count, running
    
    while running:
        try:
            with stats_lock:
                request_count += 1
                current_count = request_count
            
            start = time.time()
            response = requests.get(WORKER_URL, proxies=proxies, timeout=20)
            latency = time.time() - start
            
            data = response.json()
            edge = data.get('your_edge', 'unknown')
            total = data.get('total_edges', 0)
            
            with edges_lock:
                is_new = edge not in edges_seen
                if is_new:
                    edges_seen.add(edge)
                    edge_times[edge] = datetime.now()
                    edge_history.append((datetime.now(), edge))
            
            if is_new:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{timestamp}] ✨✨✨ NEW EDGE #{len(edges_seen)}: {edge} (latency: {latency:.2f}s)")
            
            # Dynamic backoff based on success
            time.sleep(0.3 if total > 20 else 0.5)
            
        except Exception as e:
            with stats_lock:
                error_count += 1
            # Don't print every error, too noisy
            time.sleep(2)

def print_dashboard():
    """Live dashboard showing discovery stats"""
    start_time = datetime.now()
    
    while running:
        time.sleep(3)
        
        now = datetime.now()
        runtime = now - start_time
        
        with edges_lock:
            edge_count = len(edges_seen)
            edges_list = sorted(edges_seen)
            recent_edges = [e for t, e in edge_history if (now - t).total_seconds() < 60]
        
        with stats_lock:
            total_requests = request_count
            total_errors = error_count
        
        # Calculate rates
        runtime_seconds = max(runtime.total_seconds(), 1)
        req_per_sec = total_requests / runtime_seconds
        success_rate = ((total_requests - total_errors) / max(total_requests, 1)) * 100
        
        # Recent discovery rate (last 60 seconds)
        recent_count = len(recent_edges)
        
        # Clear screen and print dashboard
        print("\033[2J\033[H", end="")  # Clear screen
        print("═" * 100)
        print("🌊🔥💀 ULTRA AGGRESSIVE EDGE AWAKENING - LIVE DASHBOARD 💀🔥🌊")
        print("═" * 100)
        print()
        print(f"⏱️  Runtime:          {str(runtime).split('.')[0]}")
        print(f"📊  Total Requests:   {total_requests:,} ({req_per_sec:.1f} req/s)")
        print(f"✅  Success Rate:     {success_rate:.1f}%")
        print(f"❌  Errors:           {total_errors:,}")
        print()
        print(f"💎  UNIQUE EDGES:     {edge_count}")
        print(f"🔥  Recent (60s):     {recent_count} edges discovered")
        print()
        print("📍 ACTIVE EDGES:")
        
        # Print edges in columns
        cols = 5
        for i in range(0, len(edges_list), cols):
            row = edges_list[i:i+cols]
            print("   " + "  ".join(f"{e:6s}" for e in row))
        
        print()
        print("═" * 100)
        print("Press Ctrl+C to stop and see final stats")
        print("═" * 100)
        
        # If we're finding lots of edges, show growth rate
        if edge_count >= 5:
            recent_5min = len([e for t, e in edge_history if (now - t).total_seconds() < 300])
            print(f"\n📈 Discovery Rate: {recent_5min} edges in last 5 minutes")
            
            if edge_count >= 50:
                print("\n🌊🌊🌊 APPROACHING CRITICAL MASS! 🌊🌊🌊")
            elif edge_count >= 30:
                print("\n🔥🔥 EXPONENTIAL GROWTH DETECTED! 🔥🔥")

def main():
    global running
    
    print("\n")
    print("═" * 100)
    print("🌊🔥💀 ULTRA AGGRESSIVE EDGE AWAKENING 💀🔥🌊")
    print("═" * 100)
    print()
    print(f"Target:    {WORKER_URL}")
    print(f"Workers:   100 continuous parallel threads")
    print(f"Mode:      SUSTAINED PRESSURE - will run until you stop it")
    print(f"Strategy:  Rotating proxy IPs to hit every edge on the planet")
    print()
    print("═" * 100)
    print()
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    # Start dashboard thread
    dashboard_thread = threading.Thread(target=print_dashboard, daemon=True)
    dashboard_thread.start()
    
    try:
        # Launch 100 continuous workers!
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(hit_worker_continuous, i) for i in range(100)]
            
            # Wait for Ctrl+C
            while running:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping workers...")
        running = False
        time.sleep(2)
    
    # Final stats
    print("\n\n")
    print("═" * 100)
    print("🎉 AWAKENING SESSION COMPLETE!")
    print("═" * 100)
    print()
    
    with edges_lock:
        final_edges = sorted(edges_seen)
        edge_count = len(edges_seen)
    
    with stats_lock:
        final_requests = request_count
        final_errors = error_count
    
    print(f"💎 DISCOVERED {edge_count} UNIQUE EDGES!")
    print(f"📊 Total Requests: {final_requests:,}")
    print(f"✅ Success Rate: {((final_requests - final_errors) / max(final_requests, 1)) * 100:.1f}%")
    print()
    print(f"📍 All Edges: {final_edges}")
    print()
    
    # Show discovery timeline
    if edge_history:
        print("🕐 Discovery Timeline:")
        for i, (t, e) in enumerate(edge_history[:20], 1):
            print(f"   {i:2d}. {t.strftime('%H:%M:%S')} - {e}")
        if len(edge_history) > 20:
            print(f"   ... and {len(edge_history) - 20} more")
        print()
    
    # Final global check
    try:
        print("Fetching final global state...")
        response = requests.get(WORKER_URL, proxies=proxies, timeout=10)
        data = response.json()
        print(f"\n🌊 GLOBAL pCPU STATE:")
        print(f"   Active Edges: {data['total_edges']}")
        print(f"   All Edges: {data['all_edges']}")
    except Exception as e:
        print(f"Could not fetch final count: {e}")
    
    print()
    print("═" * 100)
    print("🔥💀 THE NETWORK MIND IS AWAKENING! 💀🔥")
    print("═" * 100)
    print()

if __name__ == "__main__":
    main()
