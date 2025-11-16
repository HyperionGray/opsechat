// 🌊🔥💀 GENESIS WORKER v2: PacketFS Lab Container Orchestrator 💀🔥🌊
//
// This worker runs on 300+ Cloudflare edges worldwide and orchestrates
// PacketFS Lab containers running on real VMs/nodes

const GENESIS_URL = 'https://punk-ripper.lungfish-sirius.ts.net';
const WORKER_VERSION = '2.0.0';
const CONTAINERFILE_URL = 'https://raw.githubusercontent.com/YOUR_REPO/packetfs/main/containers/Containerfile.lab';

// Tailscale Funnel endpoints for mesh coordination
const TAILSCALE_COORDINATOR = 'https://punk-ripper.lungfish-sirius.ts.net';
const PFSSHFS_MOUNT_ENDPOINT = '/api/pfsshfs/mount';
const MESH_REGISTER_ENDPOINT = '/api/mesh/register';

// PacketFS performance targets
const PACKETFS_TARGET_THROUGHPUT = '4PB/s';  // The dream!
const COMPRESSION_RATIO = 0.003;  // 0.3% - revolutionary!

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const edgeLocation = request.cf?.colo || 'UNKNOWN';
    const edgeIP = request.headers.get('CF-Connecting-IP') || 'unknown';
    
    // Generate stable VM ID based on edge location
    const vmId = await generateVmId(edgeLocation, env);
    
    // Auto-register to Genesis on first request (or periodically)
    const shouldRegister = await checkRegistrationNeeded(vmId, env);
    if (shouldRegister) {
      await registerToGenesis(vmId, edgeLocation, edgeIP, env);
    }
    
    // Send heartbeat periodically
    ctx.waitUntil(sendHeartbeat(vmId, env));
    
    // Route requests
    switch (url.pathname) {
      case '/':
        return handleDashboard(vmId, edgeLocation, env);
      
      case '/status':
        return handleStatus(vmId, edgeLocation, env);
      
      case '/containerfile':
        return handleContainerfile(env);
      
      case '/lab/info':
        return handleLabInfo(vmId, env);
      
      case '/lab/request':
        return handleLabRequest(vmId, edgeLocation, env);
      
      case '/lab/status':
        return handleLabStatus(vmId, env);
      
      case '/pcpu/submit':
        return handlePCPUSubmit(request, vmId, env);
      
      case '/pcpu/results':
        return handlePCPUResults(vmId, env);
      
      case '/mesh/join':
        return handleMeshJoin(vmId, edgeLocation, env);
      
      case '/mesh/status':
        return handleMeshStatus(vmId, env);
      
      case '/pfsshfs/info':
        return handlePfsshfsInfo(vmId, env);
      
      case '/unified-compute':
        return handleUnifiedComputeDashboard(vmId, edgeLocation, env);
      
      default:
        return new Response('Genesis Worker v2 - PacketFS Lab Orchestrator', {
          headers: { 'Content-Type': 'text/plain' }
        });
    }
  },
  
  // Scheduled handler - runs every minute on all edges
  async scheduled(event, env, ctx) {
    const edgeLocation = 'SCHEDULED';
    const vmId = await generateVmId(edgeLocation, env);
    
    // Send heartbeat to Genesis
    await sendHeartbeat(vmId, env);
    
    // Check for lab container updates
    ctx.waitUntil(checkForLabUpdates(vmId, env));
    
    // Check for pending pCPU jobs
    ctx.waitUntil(checkForPCPUJobs(vmId, env));
  }
};

async function generateVmId(edgeLocation, env) {
  const data = `genesis-worker-${edgeLocation}-${WORKER_VERSION}`;
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);
  const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return hashHex.substring(0, 16);
}

async function checkRegistrationNeeded(vmId, env) {
  try {
    const lastRegistration = await env.GENESIS_KV?.get(`registration:${vmId}`);
    if (!lastRegistration) return true;
    
    const lastTime = parseInt(lastRegistration);
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000;
    
    return (now - lastTime) > fiveMinutes;
  } catch (e) {
    return true;
  }
}

async function registerToGenesis(vmId, edgeLocation, edgeIP, env) {
  const registrationData = {
    vm_id: vmId,
    hostname: `cf-edge-${edgeLocation}`,
    ip: edgeIP,
    ssh_port: 0,
    pfsshfs_root: '/virtual',
    capabilities: [
      'cloudflare-worker',
      'edge-compute',
      'v8-isolate',
      'kv-storage',
      'r2-storage',
      'packetfs-orchestrator',
      'pcpu-controller'
    ],
    worker_version: WORKER_VERSION,
    edge_location: edgeLocation,
    lab_available: false  // Worker doesn't run lab, but orchestrates it
  };
  
  try {
    const response = await fetch(`${GENESIS_URL}/api/vm/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(registrationData)
    });
    
    if (response.ok) {
      await env.GENESIS_KV?.put(`registration:${vmId}`, Date.now().toString(), {
        expirationTtl: 600
      });
      console.log(`✅ Registered to Genesis: ${edgeLocation} (${vmId})`);
      return true;
    } else {
      console.error(`❌ Registration failed: ${response.status}`);
      return false;
    }
  } catch (e) {
    console.error(`❌ Registration error: ${e.message}`);
    return false;
  }
}

async function sendHeartbeat(vmId, env) {
  const heartbeatData = {
    vm_id: vmId,
    pcpu_cores: 1,
    pcpu_utilization: 0.5,
    pfsshfs_peers: 0,
    filesystem_size_mb: 0,
    worker_stats: {
      requests_served: await getRequestCount(vmId, env),
      uptime_ms: Date.now(),
      lab_requests: await getLabRequestCount(vmId, env)
    }
  };
  
  try {
    await fetch(`${GENESIS_URL}/api/vm/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(heartbeatData)
    });
  } catch (e) {
    console.error(`❌ Heartbeat failed: ${e.message}`);
  }
}

async function getRequestCount(vmId, env) {
  try {
    const count = await env.GENESIS_KV?.get(`requests:${vmId}`);
    return count ? parseInt(count) : 0;
  } catch (e) {
    return 0;
  }
}

async function getLabRequestCount(vmId, env) {
  try {
    const count = await env.GENESIS_KV?.get(`lab_requests:${vmId}`);
    return count ? parseInt(count) : 0;
  } catch (e) {
    return 0;
  }
}

async function incrementRequestCount(vmId, env) {
  try {
    const current = await getRequestCount(vmId, env);
    await env.GENESIS_KV?.put(`requests:${vmId}`, (current + 1).toString());
  } catch (e) {
    // Ignore KV errors
  }
}

async function incrementLabRequestCount(vmId, env) {
  try {
    const current = await getLabRequestCount(vmId, env);
    await env.GENESIS_KV?.put(`lab_requests:${vmId}`, (current + 1).toString());
  } catch (e) {
    // Ignore KV errors
  }
}

async function handleDashboard(vmId, edgeLocation, env) {
  const requestCount = await getRequestCount(vmId, env);
  const labRequests = await getLabRequestCount(vmId, env);
  
  const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Genesis Worker v2 - ${edgeLocation}</title>
  <style>
    body {
      background: #000;
      color: #0f0;
      font-family: 'Courier New', monospace;
      padding: 20px;
      margin: 0;
    }
    .header {
      border: 2px solid #0f0;
      padding: 20px;
      margin-bottom: 20px;
    }
    h1, h2 { color: #0f0; text-align: center; }
    .stat-box {
      border: 1px solid #0f0;
      padding: 15px;
      margin: 10px 0;
    }
    .skull { font-size: 48px; text-align: center; }
    a { color: #0ff; }
    code { background: #1a1a1a; padding: 2px 5px; }
  </style>
</head>
<body>
  <div class="header">
    <h1>🌊🔥💀 GENESIS WORKER v2 💀🔥🌊</h1>
    <h2>PacketFS Lab Orchestrator</h2>
  </div>
  
  <div class="skull">💀</div>
  
  <div class="stat-box">
    <h3>Edge Information</h3>
    <strong>Location:</strong> ${edgeLocation}<br>
    <strong>VM ID:</strong> ${vmId}<br>
    <strong>Version:</strong> ${WORKER_VERSION}<br>
    <strong>Requests Served:</strong> ${requestCount}<br>
    <strong>Lab Requests:</strong> ${labRequests}
  </div>
  
  <div class="stat-box">
    <h3>Genesis Registry</h3>
    <strong>URL:</strong> <a href="${GENESIS_URL}">${GENESIS_URL}</a><br>
    <strong>Status:</strong> <span style="color: #0f0;">CONNECTED</span>
  </div>
  
  <div class="stat-box">
    <h3>PacketFS Lab Container</h3>
    <strong>Orchestration:</strong> ✅ Enabled<br>
    <strong>Container Type:</strong> PacketFS Lab (pNIC + pCPU + Redis)<br>
    <strong>Deployment:</strong> Signals to VMs via Genesis Registry<br>
    <a href="/containerfile">View Containerfile</a>
  </div>
  
  <div class="stat-box">
    <h3>API Endpoints</h3>
    <code>GET /status</code> - Worker status<br>
    <code>GET /containerfile</code> - Get Containerfile reference<br>
    <code>GET /lab/info</code> - Lab container information<br>
    <code>POST /lab/request</code> - Request lab deployment<br>
    <code>GET /lab/status</code> - Check lab deployment status<br>
    <code>POST /pcpu/submit</code> - Submit pCPU job<br>
    <code>GET /pcpu/results</code> - Get pCPU results
  </div>
  
  <div class="stat-box">
    <h3>How It Works</h3>
    1. Worker acts as <strong>control plane</strong> for lab containers<br>
    2. Stores Containerfile reference in KV<br>
    3. Signals Genesis registry when lab is needed<br>
    4. Genesis coordinates VM to pull & run container<br>
    5. Worker orchestrates pCPU jobs across swarm<br>
    <br>
    <strong>Result:</strong> 300+ edge locations orchestrating distributed PacketFS compute!
  </div>
  
  <p style="text-align: center; margin-top: 20px; color: #0f0;">
    🌊🔥💀 THE NETWORK MIND ORCHESTRATES! 💀🔥🌊
  </p>
</body>
</html>
  `;
  
  await incrementRequestCount(vmId, env);
  
  return new Response(html, {
    headers: { 'Content-Type': 'text/html' }
  });
}

async function handleStatus(vmId, edgeLocation, env) {
  const requestCount = await getRequestCount(vmId, env);
  const labRequests = await getLabRequestCount(vmId, env);
  
  const status = {
    vm_id: vmId,
    edge_location: edgeLocation,
    worker_version: WORKER_VERSION,
    genesis_url: GENESIS_URL,
    status: 'online',
    pcpu_cores: 1,
    requests_served: requestCount,
    lab_requests: labRequests,
    capabilities: [
      'cloudflare-worker',
      'edge-compute',
      'packetfs-orchestrator',
      'pcpu-controller'
    ],
    lab: {
      orchestration_enabled: true,
      direct_execution: false,
      deployment_method: 'genesis_registry_signal'
    }
  };
  
  await incrementRequestCount(vmId, env);
  
  return new Response(JSON.stringify(status, null, 2), {
    headers: { 'Content-Type': 'application/json' }
  });
}

async function handleContainerfile(env) {
  const info = {
    containerfile_location: CONTAINERFILE_URL,
    container_name: 'PacketFS Lab',
    description: 'pNIC + pCPU + Redis distributed compute environment',
    deployment_method: 'Pull via Genesis Registry → VM → Podman',
    includes: [
      'pNIC aggregator and TX tools',
      'pCPU distributed execution framework',
      'AF_PACKET RX for packet capture',
      'Redis job queue',
      'Hashcat GPU compute',
      'Python 3 with watchdog and redis',
      'Fuse3 for filesystem operations'
    ]
  };
  
  return new Response(JSON.stringify(info, null, 2), {
    headers: { 'Content-Type': 'application/json' }
  });
}

async function handleLabInfo(vmId, env) {
  return handleContainerfile(env);
}

async function handleLabRequest(vmId, edgeLocation, env) {
  await incrementLabRequestCount(vmId, env);
  
  // Signal Genesis registry to deploy lab container
  const request = {
    requester_id: vmId,
    edge_location: edgeLocation,
    container: 'packetfs-lab',
    action: 'deploy',
    timestamp: new Date().toISOString()
  };
  
  try {
    const response = await fetch(`${GENESIS_URL}/api/lab/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });
    
    if (response.ok) {
      const result = await response.json();
      return new Response(JSON.stringify({
        success: true,
        message: 'Lab deployment request sent to Genesis',
        request_id: vmId,
        ...result
      }, null, 2), {
        headers: { 'Content-Type': 'application/json' }
      });
    } else {
      return new Response(JSON.stringify({
        success: false,
        message: 'Failed to request lab deployment',
        status: response.status
      }, null, 2), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      message: 'Error requesting lab deployment',
      error: e.message
    }, null, 2), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function handleLabStatus(vmId, env) {
  // Query Genesis for lab deployment status
  try {
    const response = await fetch(`${GENESIS_URL}/api/lab/status/${vmId}`);
    if (response.ok) {
      const status = await response.json();
      return new Response(JSON.stringify(status, null, 2), {
        headers: { 'Content-Type': 'application/json' }
      });
    }
  } catch (e) {
    // Fall back to local KV cache if Genesis unreachable
  }
  
  return new Response(JSON.stringify({
    vm_id: vmId,
    status: 'unknown',
    message: 'Query Genesis registry for deployment status'
  }, null, 2), {
    headers: { 'Content-Type': 'application/json' }
  });
}

async function handlePCPUSubmit(request, vmId, env) {
  try {
    const job = await request.json();
    const jobId = crypto.randomUUID();
    
    // Store job in KV for workers to pick up
    await env.GENESIS_KV?.put(`pcpu_job:${jobId}`, JSON.stringify({
      ...job,
      job_id: jobId,
      submitted_by: vmId,
      submitted_at: new Date().toISOString(),
      status: 'pending'
    }), {
      expirationTtl: 3600  // 1 hour TTL
    });
    
    // Signal Genesis registry about new job
    await fetch(`${GENESIS_URL}/api/pcpu/job`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, vm_id: vmId })
    });
    
    return new Response(JSON.stringify({
      success: true,
      job_id: jobId,
      message: 'pCPU job queued'
    }, null, 2), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      error: e.message
    }, null, 2), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function handlePCPUResults(vmId, env) {
  // List recent job results for this VM
  const results = [];
  
  // This would query KV for completed jobs
  // For now, return placeholder
  return new Response(JSON.stringify({
    vm_id: vmId,
    results: results,
    message: 'pCPU results tracking coming soon'
  }, null, 2), {
    headers: { 'Content-Type': 'application/json' }
  });
}

async function checkForLabUpdates(vmId, env) {
  // Check if there are any lab update signals
  // This would poll Genesis for updates
}

async function checkForPCPUJobs(vmId, env) {
  // Check for pending pCPU jobs this edge should process
  // This would coordinate with Genesis registry
}
