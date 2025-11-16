// 🌊🔥💀 GENESIS WORKER: Auto-register Cloudflare Edges to Genesis Registry 💀🔥🌊
//
// This worker runs on 300+ Cloudflare edges worldwide
// Each edge auto-registers to Genesis and becomes a pCPU node!

const GENESIS_URL = 'https://punk-ripper.lungfish-sirius.ts.net';
const WORKER_VERSION = '1.0.0';

// Edge state stored in KV (persists across requests)
// const EDGE_STATE = GENESIS_KV; // Bind this in wrangler.toml

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
      
      case '/genesis/register':
        return handleManualRegister(vmId, edgeLocation, edgeIP, env);
      
      case '/pull-vm':
        return handlePullVM(vmId, env);
      
      default:
        return new Response('Genesis Worker - Edge pCPU Node', {
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
    
    // Check for VM pull updates
    ctx.waitUntil(checkForUpdates(vmId, env));
  }
};

async function generateVmId(edgeLocation, env) {
  // Generate stable ID based on edge location
  const data = `genesis-worker-${edgeLocation}-${WORKER_VERSION}`;
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);
  const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return hashHex.substring(0, 16);
}

async function checkRegistrationNeeded(vmId, env) {
  // Check if registered in last 5 minutes
  try {
    const lastRegistration = await env.GENESIS_KV?.get(`registration:${vmId}`);
    if (!lastRegistration) return true;
    
    const lastTime = parseInt(lastRegistration);
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000;
    
    return (now - lastTime) > fiveMinutes;
  } catch (e) {
    return true; // Register if KV check fails
  }
}

async function registerToGenesis(vmId, edgeLocation, edgeIP, env) {
  const registrationData = {
    vm_id: vmId,
    hostname: `cf-edge-${edgeLocation}`,
    ip: edgeIP,
    ssh_port: 0, // Workers don't have SSH
    pfsshfs_root: '/virtual', // Virtual filesystem
    capabilities: [
      'cloudflare-worker',
      'edge-compute',
      'v8-isolate',
      'kv-storage',
      'r2-storage'
    ],
    worker_version: WORKER_VERSION,
    edge_location: edgeLocation
  };
  
  try {
    const response = await fetch(`${GENESIS_URL}/api/vm/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(registrationData)
    });
    
    if (response.ok) {
      // Store registration time
      await env.GENESIS_KV?.put(`registration:${vmId}`, Date.now().toString(), {
        expirationTtl: 600 // 10 minutes
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
    pcpu_cores: 1, // Each worker is 1 isolate
    pcpu_utilization: 0.5, // Estimate
    pfsshfs_peers: 0,
    filesystem_size_mb: 0,
    worker_stats: {
      requests_served: await getRequestCount(vmId, env),
      uptime_ms: Date.now() // Approximate
    }
  };
  
  try {
    const response = await fetch(`${GENESIS_URL}/api/vm/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(heartbeatData)
    });
    
    if (response.ok) {
      console.log(`💓 Heartbeat sent for ${vmId}`);
    }
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

async function incrementRequestCount(vmId, env) {
  try {
    const current = await getRequestCount(vmId, env);
    await env.GENESIS_KV?.put(`requests:${vmId}`, (current + 1).toString());
  } catch (e) {
    // Ignore KV errors
  }
}

async function handleDashboard(vmId, edgeLocation, env) {
  const requestCount = await getRequestCount(vmId, env);
  
  const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Genesis Worker - ${edgeLocation}</title>
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
  </style>
</head>
<body>
  <div class="header">
    <h1>🌊🔥💀 GENESIS WORKER 💀🔥🌊</h1>
    <h2>Cloudflare Edge pCPU Node</h2>
  </div>
  
  <div class="skull">💀</div>
  
  <div class="stat-box">
    <h3>Edge Information</h3>
    <strong>Location:</strong> ${edgeLocation}<br>
    <strong>VM ID:</strong> ${vmId}<br>
    <strong>Version:</strong> ${WORKER_VERSION}<br>
    <strong>Requests Served:</strong> ${requestCount}
  </div>
  
  <div class="stat-box">
    <h3>Genesis Registry</h3>
    <strong>URL:</strong> <a href="${GENESIS_URL}">${GENESIS_URL}</a><br>
    <strong>Status:</strong> <span style="color: #0f0;">CONNECTED</span>
  </div>
  
  <div class="stat-box">
    <h3>Capabilities</h3>
    ✅ Cloudflare Worker<br>
    ✅ Edge Compute<br>
    ✅ V8 Isolate<br>
    ✅ KV Storage<br>
    ✅ R2 Storage
  </div>
  
  <div class="stat-box">
    <h3>Endpoints</h3>
    <a href="/status">/status</a> - Worker status<br>
    <a href="/genesis/register">/genesis/register</a> - Force re-registration<br>
    <a href="/pull-vm">/pull-vm</a> - Pull PacketFS VM
  </div>
  
  <p style="text-align: center; margin-top: 20px; color: #0f0;">
    🌊🔥💀 THE NETWORK MIND GROWS! 💀🔥🌊
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
  
  const status = {
    vm_id: vmId,
    edge_location: edgeLocation,
    worker_version: WORKER_VERSION,
    genesis_url: GENESIS_URL,
    status: 'online',
    pcpu_cores: 1,
    requests_served: requestCount,
    capabilities: [
      'cloudflare-worker',
      'edge-compute',
      'v8-isolate',
      'kv-storage',
      'r2-storage'
    ]
  };
  
  await incrementRequestCount(vmId, env);
  
  return new Response(JSON.stringify(status, null, 2), {
    headers: { 'Content-Type': 'application/json' }
  });
}

async function handleManualRegister(vmId, edgeLocation, edgeIP, env) {
  const success = await registerToGenesis(vmId, edgeLocation, edgeIP, env);
  
  return new Response(JSON.stringify({
    success,
    message: success ? 'Registered to Genesis' : 'Registration failed',
    vm_id: vmId
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}

async function handlePullVM(vmId, env) {
  // Pull PacketFS VM from Genesis
  // This is a placeholder for actual VM pulling logic
  
  const response = {
    vm_id: vmId,
    action: 'pull-vm',
    message: 'VM pulling not yet implemented',
    next_steps: [
      'Connect to Genesis Registry',
      'Request VM image from R2',
      'Extract IPROG formula',
      'Bootstrap PacketFS environment'
    ]
  };
  
  return new Response(JSON.stringify(response, null, 2), {
    headers: { 'Content-Type': 'application/json' }
  });
}

async function checkForUpdates(vmId, env) {
  // Check Genesis for VM updates
  try {
    const response = await fetch(`${GENESIS_URL}/api/vm/updates/${vmId}`);
    if (response.ok) {
      const updates = await response.json();
      if (updates.has_updates) {
        console.log(`📦 Updates available for ${vmId}`);
        // TODO: Pull and apply updates
      }
    }
  } catch (e) {
    console.error(`❌ Update check failed: ${e.message}`);
  }
}
