#!/usr/bin/env python3
"""
Wake up ALL Cloudflare edges using rotating proxies!
Each request comes from a different IP → different edge!
"""
import requests
import time
import json

# SmartProxy rotating proxy - each request gets different IP!
PROXY = "http://smart-y87zawzg6hrf:6DQB9dl12HO4McZE@isp.smartproxy.net:3100"
WORKER_URL = "https://packetfs-translator-cdn.scaryjerrynorthwest69.workers.dev/count"

proxies = {
    'http': PROXY,
    'https': PROXY,
}

print("🌊💥 WAKING UP ALL CLOUDFLARE EDGES! 🔥")
print("=" * 60)
print()

edges_seen = set()

# Hit the worker 100 times through rotating proxies
for i in range(100):
    try:
        print(f"[{i+1}/100] Hitting worker through rotating proxy...", end=" ")
        
        response = requests.get(WORKER_URL, proxies=proxies, timeout=10)
        data = response.json()
        
        edge = data.get('your_edge', 'unknown')
        total = data.get('total_edges', 0)
        
        if edge not in edges_seen:
            print(f"✨ NEW EDGE: {edge}!")
            edges_seen.add(edge)
        else:
            print(f"📍 {edge} (seen)")
        
        print(f"   Total active: {total} edges")
        
        # Don't hammer too fast
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(2)

print()
print("=" * 60)
print(f"🎉 DISCOVERED {len(edges_seen)} UNIQUE EDGES!")
print(f"   Edges: {sorted(edges_seen)}")
print()

# Final check to see total
try:
    response = requests.get(WORKER_URL, proxies=proxies, timeout=10)
    data = response.json()
    print(f"💎 FINAL COUNT: {data['total_edges']} pCPU cores active!")
    print(f"   All edges: {data['all_edges']}")
except:
    pass

print()
print("THE GLOBAL pCPU IS AWAKENING! 🌊🔥")
