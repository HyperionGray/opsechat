#!/usr/bin/env python3
"""
🌊🔥💀 HAPROXY VM SYNC 💀🔥🌊

Dynamically updates HAProxy backends as VMs register to Genesis!
Uses HAProxy Runtime API to add/remove servers without restart!
"""
import requests
import time
import subprocess
import socket
from datetime import datetime

GENESIS_URL = "http://localhost:9001"
HAPROXY_SOCKET = "/run/haproxy/admin.sock"
SYNC_INTERVAL = 5  # seconds

# Port ranges for each service
PORT_RANGES = {
    'pcpu': (10000, 19999),
    'pfsshfs': (20000, 29999),
    'transfer': (30000, 31999),
}

def haproxy_cmd(cmd):
    """Send command to HAProxy via socket"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(HAPROXY_SOCKET)
        sock.send(f"{cmd}\n".encode())
        response = sock.recv(4096).decode()
        sock.close()
        return response
    except Exception as e:
        print(f"HAProxy command failed: {e}")
        return None

def get_registered_vms():
    """Fetch all registered VMs from Genesis"""
    try:
        response = requests.get(f"{GENESIS_URL}/api/vms", timeout=5)
        data = response.json()
        return data.get('vms', {})
    except Exception as e:
        print(f"Failed to fetch VMs: {e}")
        return {}

def get_haproxy_servers(backend):
    """Get current servers in HAProxy backend"""
    response = haproxy_cmd(f"show servers state {backend}")
    if not response:
        return set()
    
    servers = set()
    for line in response.split('\n')[1:]:  # Skip header
        if line.strip():
            parts = line.split()
            if len(parts) >= 2:
                servers.add(parts[1])  # Server name
    return servers

def assign_port(vm_id, service_type):
    """Assign a port from the service's range"""
    # Simple hash-based assignment
    port_min, port_max = PORT_RANGES[service_type]
    port_range = port_max - port_min + 1
    vm_hash = int(vm_id, 16) if vm_id.isalnum() else hash(vm_id)
    port = port_min + (vm_hash % port_range)
    return port

def sync_backends():
    """Sync HAProxy backends with registered VMs"""
    vms = get_registered_vms()
    
    if not vms:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] No VMs registered")
        return
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Syncing {len(vms)} VMs...")
    
    # Sync pCPU workers
    backend = 'pcpu_workers'
    haproxy_servers = get_haproxy_servers(backend)
    
    for vm_id, vm_info in vms.items():
        if vm_info.get('status') != 'online':
            continue
        
        server_name = f"vm_{vm_id}"
        vm_ip = vm_info.get('ip', '127.0.0.1')
        vm_port = assign_port(vm_id, 'pcpu')
        
        if server_name not in haproxy_servers:
            # Add new server
            cmd = f"add server {backend}/{server_name} {vm_ip}:{vm_port} check"
            result = haproxy_cmd(cmd)
            print(f"  ✨ Added {server_name} -> {vm_ip}:{vm_port}")
        else:
            # Enable if disabled
            cmd = f"enable server {backend}/{server_name}"
            haproxy_cmd(cmd)
    
    # Sync PFSSHFS access
    backend = 'pfsshfs_vms'
    haproxy_servers = get_haproxy_servers(backend)
    
    for vm_id, vm_info in vms.items():
        if vm_info.get('status') != 'online':
            continue
        
        server_name = f"ssh_{vm_id}"
        vm_ip = vm_info.get('ip', '127.0.0.1')
        ssh_port = vm_info.get('ssh_port', 22)
        
        if server_name not in haproxy_servers:
            cmd = f"add server {backend}/{server_name} {vm_ip}:{ssh_port} check"
            result = haproxy_cmd(cmd)
            print(f"  🔐 Added SSH {server_name} -> {vm_ip}:{ssh_port}")
    
    # Sync PacketFS Transfer workers
    backend = 'pfs_transfer_workers'
    haproxy_servers = get_haproxy_servers(backend)
    
    for vm_id, vm_info in vms.items():
        if vm_info.get('status') != 'online':
            continue
        
        server_name = f"transfer_{vm_id}"
        vm_ip = vm_info.get('ip', '127.0.0.1')
        transfer_port = assign_port(vm_id, 'transfer')
        
        if server_name not in haproxy_servers:
            cmd = f"add server {backend}/{server_name} {vm_ip}:{transfer_port} check"
            result = haproxy_cmd(cmd)
            print(f"  📦 Added Transfer {server_name} -> {vm_ip}:{transfer_port}")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sync complete! {len(vms)} VMs active")

def main():
    print("🌊🔥💀 HAPROXY VM SYNC DAEMON 💀🔥🌊")
    print()
    print(f"Genesis URL: {GENESIS_URL}")
    print(f"HAProxy Socket: {HAPROXY_SOCKET}")
    print(f"Sync Interval: {SYNC_INTERVAL}s")
    print()
    print("Port Assignments:")
    for service, (start, end) in PORT_RANGES.items():
        print(f"  {service:12s}: {start:5d} - {end:5d}")
    print()
    print("Starting sync loop...")
    print("=" * 60)
    print()
    
    while True:
        try:
            sync_backends()
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {e}")
        
        time.sleep(SYNC_INTERVAL)

if __name__ == "__main__":
    main()
