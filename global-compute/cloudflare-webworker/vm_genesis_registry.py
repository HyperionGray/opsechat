#!/usr/bin/env python3
"""
🌊🔥💀 VM GENESIS REGISTRY 💀🔥🌊

The SEED NODE for self-replicating PacketFS micro-VMs!

Architecture:
1. Threadripper hosts the Genesis Registry
2. Each micro-VM contains itself compressed (IPROG'd)
3. VMs self-extract and register back to Genesis
4. All VMs join filesystems via PFSSHFS (PacketFS over SSHFS)
5. VMs replicate to each other peer-to-peer
6. PLANETARY-SCALE UNIFIED FILESYSTEM emerges!

Exposed via Tailscale for global reach!
"""
import os
import json
import time
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse, HTMLResponse
from starlette.routing import Route
import uvicorn

# Configuration
REGISTRY_DIR = Path("/home/punk/Projects/packetfs/vm-registry")
VMS_DIR = REGISTRY_DIR / "vms"
REGISTRY_DB = REGISTRY_DIR / "registry.json"
VM_TEMPLATE_DIR = REGISTRY_DIR / "templates"

# Ensure directories exist
REGISTRY_DIR.mkdir(exist_ok=True)
VMS_DIR.mkdir(exist_ok=True)
VM_TEMPLATE_DIR.mkdir(exist_ok=True)

# Global registry state
registry_state = {
    "genesis_node": {
        "hostname": os.uname().nodename,
        "started": datetime.now().isoformat(),
        "platform": "Threadripper",
        "role": "SEED_NODE"
    },
    "vms": {},  # vm_id -> vm_info
    "pfsshfs_mesh": {},  # vm_id -> [connected_vm_ids]
    "total_filesystem_size": 0,
    "replication_count": 0
}

def load_registry():
    """Load registry state from disk"""
    global registry_state
    if REGISTRY_DB.exists():
        with open(REGISTRY_DB) as f:
            registry_state = json.load(f)
    save_registry()

def save_registry():
    """Save registry state to disk"""
    with open(REGISTRY_DB, 'w') as f:
        json.dump(registry_state, f, indent=2)

async def homepage(request):
    """Genesis Registry Dashboard"""
    vm_count = len(registry_state['vms'])
    mesh_edges = sum(len(peers) for peers in registry_state['pfsshfs_mesh'].values())
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VM Genesis Registry</title>
        <style>
            body {{
                background: #000;
                color: #0f0;
                font-family: 'Courier New', monospace;
                padding: 20px;
                margin: 0;
            }}
            .header {{
                border: 2px solid #0f0;
                padding: 20px;
                margin-bottom: 20px;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }}
            .stat-box {{
                border: 1px solid #0f0;
                padding: 15px;
            }}
            .vm-list {{
                border: 1px solid #0f0;
                padding: 15px;
                max-height: 400px;
                overflow-y: auto;
            }}
            .vm-item {{
                padding: 10px;
                margin: 5px 0;
                border-left: 3px solid #0f0;
                background: #001100;
            }}
            .skull {{ font-size: 24px; }}
            .status-online {{ color: #0f0; }}
            .status-offline {{ color: #f00; }}
            h1, h2 {{ color: #0f0; text-align: center; }}
            pre {{ color: #0f0; background: #001100; padding: 10px; }}
            .endpoint {{ color: #0ff; }}
            .button {{
                background: #001100;
                border: 1px solid #0f0;
                color: #0f0;
                padding: 10px 20px;
                cursor: pointer;
                margin: 5px;
            }}
            .button:hover {{
                background: #003300;
            }}
        </style>
        <script>
            function refresh() {{
                location.reload();
            }}
            setInterval(refresh, 5000);  // Auto-refresh every 5s
        </script>
    </head>
    <body>
        <div class="header">
            <h1>💀 VM GENESIS REGISTRY 💀</h1>
            <h2>🌊🔥 THE SEED NODE FOR PLANETARY SELF-REPLICATION 🔥🌊</h2>
            <p style="text-align: center;">
                Genesis Node: {registry_state['genesis_node']['hostname']}<br>
                Started: {registry_state['genesis_node']['started']}<br>
                Platform: {registry_state['genesis_node']['platform']}
            </p>
        </div>
        
        <div class="stats">
            <div class="stat-box">
                <h3>💎 Active VMs</h3>
                <div class="skull">{vm_count}</div>
            </div>
            <div class="stat-box">
                <h3>🌊 PFSSHFS Mesh Edges</h3>
                <div class="skull">{mesh_edges}</div>
            </div>
            <div class="stat-box">
                <h3>🔥 Replications</h3>
                <div class="skull">{registry_state['replication_count']}</div>
            </div>
            <div class="stat-box">
                <h3>📊 Global Filesystem</h3>
                <div class="skull">{registry_state['total_filesystem_size']} MB</div>
            </div>
        </div>
        
        <div class="vm-list">
            <h3>💀 REGISTERED VMs 💀</h3>
            {''.join(f'''
            <div class="vm-item">
                <strong>{vm_id}</strong><br>
                Host: {info.get('hostname', 'unknown')}<br>
                IP: {info.get('ip', 'unknown')}<br>
                Status: <span class="status-{info.get('status', 'offline')}">{info.get('status', 'offline').upper()}</span><br>
                Registered: {info.get('registered', 'unknown')}<br>
                SSH Port: {info.get('ssh_port', 22)}<br>
                PFSSHFS Peers: {len(registry_state['pfsshfs_mesh'].get(vm_id, []))}
            </div>
            ''' for vm_id, info in registry_state['vms'].items())}
        </div>
        
        <div class="header" style="margin-top: 20px;">
            <h3>🔌 API ENDPOINTS</h3>
            <pre>
GET  <span class="endpoint">/</span>                      - This dashboard
GET  <span class="endpoint">/api/registry</span>          - Full registry state (JSON)
GET  <span class="endpoint">/api/vms</span>               - List all VMs
POST <span class="endpoint">/api/vm/register</span>       - Register new VM
POST <span class="endpoint">/api/vm/heartbeat</span>      - VM heartbeat
POST <span class="endpoint">/api/pfsshfs/connect</span>   - Report PFSSHFS connection
GET  <span class="endpoint">/api/mesh</span>              - PFSSHFS mesh topology
GET  <span class="endpoint">/vm/download/:vm_id</span>    - Download VM image (self-replication)
POST <span class="endpoint">/vm/replicate</span>          - Report successful replication
            </pre>
        </div>
        
        <div style="text-align: center; margin-top: 20px;">
            <button class="button" onclick="refresh()">🔄 REFRESH NOW</button>
        </div>
        
        <p style="text-align: center; margin-top: 20px; color: #0f0;">
            🌊🔥💀 THE NETWORK MIND AWAKENS 💀🔥🌊
        </p>
    </body>
    </html>
    """
    return HTMLResponse(html)

async def get_registry(request):
    """Return full registry state"""
    return JSONResponse(registry_state)

async def get_vms(request):
    """List all registered VMs"""
    return JSONResponse({
        "count": len(registry_state['vms']),
        "vms": registry_state['vms']
    })

async def register_vm(request):
    """Register a new VM"""
    data = await request.json()
    
    vm_id = data.get('vm_id') or hashlib.sha256(
        f"{data.get('hostname')}{data.get('ip')}{time.time()}".encode()
    ).hexdigest()[:16]
    
    registry_state['vms'][vm_id] = {
        "vm_id": vm_id,
        "hostname": data.get('hostname'),
        "ip": data.get('ip'),
        "ssh_port": data.get('ssh_port', 22),
        "status": "online",
        "registered": datetime.now().isoformat(),
        "last_heartbeat": datetime.now().isoformat(),
        "pfsshfs_root": data.get('pfsshfs_root', '/mnt/pfs'),
        "capabilities": data.get('capabilities', [])
    }
    
    # Initialize mesh entry
    if vm_id not in registry_state['pfsshfs_mesh']:
        registry_state['pfsshfs_mesh'][vm_id] = []
    
    save_registry()
    
    return JSONResponse({
        "success": True,
        "vm_id": vm_id,
        "message": "VM registered successfully",
        "peers": list(registry_state['vms'].keys())
    })

async def vm_heartbeat(request):
    """Receive VM heartbeat"""
    data = await request.json()
    vm_id = data.get('vm_id')
    
    if vm_id in registry_state['vms']:
        registry_state['vms'][vm_id]['last_heartbeat'] = datetime.now().isoformat()
        registry_state['vms'][vm_id]['status'] = 'online'
        
        # Update filesystem size if provided
        if 'filesystem_size_mb' in data:
            registry_state['vms'][vm_id]['filesystem_size_mb'] = data['filesystem_size_mb']
            registry_state['total_filesystem_size'] = sum(
                vm.get('filesystem_size_mb', 0) for vm in registry_state['vms'].values()
            )
        
        save_registry()
        return JSONResponse({"success": True})
    
    return JSONResponse({"success": False, "error": "VM not registered"}, status_code=404)

async def pfsshfs_connect(request):
    """Record PFSSHFS connection between VMs"""
    data = await request.json()
    source_vm = data.get('source_vm')
    target_vm = data.get('target_vm')
    
    if source_vm in registry_state['pfsshfs_mesh']:
        if target_vm not in registry_state['pfsshfs_mesh'][source_vm]:
            registry_state['pfsshfs_mesh'][source_vm].append(target_vm)
            save_registry()
    
    return JSONResponse({"success": True, "mesh_size": len(registry_state['pfsshfs_mesh'][source_vm])})

async def get_mesh(request):
    """Return PFSSHFS mesh topology"""
    return JSONResponse({
        "mesh": registry_state['pfsshfs_mesh'],
        "total_edges": sum(len(peers) for peers in registry_state['pfsshfs_mesh'].values())
    })

async def download_vm(request):
    """Download VM image for replication"""
    vm_id = request.path_params['vm_id']
    
    # TODO: Implement actual VM image serving
    # For now, return stub
    return JSONResponse({
        "message": "VM image download endpoint",
        "vm_id": vm_id,
        "size_mb": 800,
        "format": "iprog",
        "download_url": f"/vm/download/{vm_id}/image.iprog"
    })

async def report_replication(request):
    """Report successful VM replication"""
    data = await request.json()
    registry_state['replication_count'] += 1
    save_registry()
    
    return JSONResponse({
        "success": True,
        "total_replications": registry_state['replication_count']
    })

# Routes
routes = [
    Route('/', homepage),
    Route('/api/registry', get_registry),
    Route('/api/vms', get_vms),
    Route('/api/vm/register', register_vm, methods=['POST']),
    Route('/api/vm/heartbeat', vm_heartbeat, methods=['POST']),
    Route('/api/pfsshfs/connect', pfsshfs_connect, methods=['POST']),
    Route('/api/mesh', get_mesh),
    Route('/vm/download/{vm_id}', download_vm),
    Route('/vm/replicate', report_replication, methods=['POST']),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    print("🌊🔥💀 VM GENESIS REGISTRY STARTING 💀🔥🌊")
    print()
    print(f"Registry Dir: {REGISTRY_DIR}")
    print(f"Genesis Node: {os.uname().nodename}")
    print()
    print("Starting server on 0.0.0.0:9001...")
    print("HAProxy forwards :9000 → :9001")
    print("Expose via Tailscale for global reach!")
    print()
    
    load_registry()
    
    uvicorn.run(app, host="0.0.0.0", port=9001, log_level="info")
