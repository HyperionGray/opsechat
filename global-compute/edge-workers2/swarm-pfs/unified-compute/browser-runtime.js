/**
 * PacketFS Browser Runtime
 * Wasm + Service Worker for distributed computation
 * Executes PacketFS programs on user's browser = FREE COMPUTE
 */

// ============================================================================
// SERVICE WORKER: Job dispatcher and result collector
// ============================================================================

const PACKETFS_COMPUTE_CHANNEL = 'packetfs:compute';
const COORDINATOR_URL = 'wss://coordinator.packetfs.global';

self.addEventListener('install', (event) => {
  console.log('[PFS Worker] Installing...');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[PFS Worker] Activating...');
  event.waitUntil(clients.claim());
});

// Main message handler - receives jobs from dispatcher
self.addEventListener('message', async (event) => {
  const { type, jobId, program, timeout } = event.data;
  
  if (type === 'execute') {
    try {
      // Execute PacketFS program
      const result = await executePacketFSProgram(program, timeout);
      
      // Send result back to client
      event.ports[0].postMessage({
        type: 'result',
        jobId,
        success: true,
        data: result,
        executionTimeMs: result.executionTimeMs,
        bytesProcessed: result.bytesProcessed
      });
    } catch (error) {
      event.ports[0].postMessage({
        type: 'result',
        jobId,
        success: false,
        error: error.message
      });
    }
  } else if (type === 'health') {
    event.ports[0].postMessage({ status: 'healthy', capabilities: getBrowserCapabilities() });
  }
});

// Fetch handler for HTTP-based job distribution
self.addEventListener('fetch', async (event) => {
  const url = new URL(event.request.url);
  
  // POST /execute - execute a job
  if (event.request.method === 'POST' && url.pathname === '/execute') {
    event.respondWith(handleJobExecution(event.request));
  }
  
  // GET /health - health check
  if (event.request.method === 'GET' && url.pathname === '/health') {
    event.respondWith(
      new Response(
        JSON.stringify({
          status: 'healthy',
          version: '1.0.0',
          capabilities: getBrowserCapabilities()
        }),
        { headers: { 'Content-Type': 'application/json' } }
      )
    );
  }
});

/**
 * Handle HTTP job execution request
 */
async function handleJobExecution(request) {
  try {
    const jobPayload = await request.json();
    const { jobId, program, timeout } = jobPayload;
    
    // Execute program with timeout
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Execution timeout')), timeout || 30000)
    );
    
    const executionPromise = executePacketFSProgram(program, timeout);
    const result = await Promise.race([executionPromise, timeoutPromise]);
    
    return new Response(
      JSON.stringify({
        success: true,
        jobId,
        results: result,
        executionTimeMs: result.executionTimeMs,
        bytesProcessed: result.bytesProcessed
      }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ success: false, error: error.message }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

/**
 * Execute a PacketFS program
 */
async function executePacketFSProgram(program, timeout) {
  const startTime = performance.now();
  const results = {};
  let bytesProcessed = 0;
  
  try {
    // Fetch data from URL
    const dataUrl = program.data_url;
    let offset = program.offset || 0;
    let length = program.length || null;
    
    const headers = {};
    if (offset !== undefined && length !== undefined) {
      headers['Range'] = `bytes=${offset}-${offset + length - 1}`;
    }
    
    const dataResponse = await fetch(dataUrl, { headers });
    const buffer = await dataResponse.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    bytesProcessed = bytes.length;
    
    // Execute operations based on program
    const operations = program.operations || program.ops || [];
    
    for (const op of operations) {
      const opResult = executeOperation(op, bytes);
      results[op.op] = opResult;
    }
    
  } catch (error) {
    console.error('[PFS] Execution error:', error);
    throw error;
  }
  
  const executionTimeMs = performance.now() - startTime;
  
  return {
    results,
    executionTimeMs,
    bytesProcessed,
    success: true
  };
}

/**
 * Execute a single PacketFS operation
 */
function executeOperation(op, bytes) {
  const { operation, imm, offset, length } = op;
  
  // Extract slice
  const start = offset || 0;
  const end = length ? start + length : bytes.length;
  const slice = bytes.slice(start, end);
  
  switch (operation) {
    case 'counteq': {
      // Count bytes equal to immediate
      let count = 0;
      const needle = imm & 0xFF;
      for (let i = 0; i < slice.length; i++) {
        if (slice[i] === needle) count++;
      }
      return { op: 'counteq', count, bytesScanned: slice.length };
    }
    
    case 'crc32c': {
      // CRC32C checksum
      let crc = 0xFFFFFFFF;
      for (let i = 0; i < slice.length; i++) {
        crc ^= slice[i];
        for (let j = 0; j < 8; j++) {
          crc = (crc >>> 1) ^ (0x82F63B78 & (-(crc & 1)));
        }
      }
      return { op: 'crc32c', checksum: (crc ^ 0xFFFFFFFF) >>> 0, bytesProcessed: slice.length };
    }
    
    case 'fnv64': {
      // FNV-1a 64-bit hash
      let hash = 0xcbf29ce484222325n;
      const prime = 0x100000001b3n;
      for (let i = 0; i < slice.length; i++) {
        hash ^= BigInt(slice[i]);
        hash = (hash * prime) & 0xFFFFFFFFFFFFFFFFn;
      }
      return { op: 'fnv64', hash: hash.toString(16), bytesHashed: slice.length };
    }
    
    case 'xor': {
      // XOR with immediate
      const k = imm & 0xFF;
      let result = 0;
      for (let i = 0; i < slice.length; i++) {
        result ^= (slice[i] ^ k);
      }
      return { op: 'xor', result, bytesProcessed: slice.length };
    }
    
    case 'add': {
      // Add with immediate (mod 256)
      const k = imm & 0xFF;
      let result = 0;
      for (let i = 0; i < slice.length; i++) {
        result += (slice[i] + k) & 0xFF;
      }
      return { op: 'add', result, bytesProcessed: slice.length };
    }
    
    default:
      throw new Error(`Unknown operation: ${operation}`);
  }
}

/**
 * Get browser capabilities
 */
function getBrowserCapabilities() {
  return {
    hardwareConcurrency: navigator.hardwareConcurrency || 4,
    deviceMemory: navigator.deviceMemory || 4,
    maxStorage: Math.min(1024 * 1024 * 1024, navigator.storage?.estimate?.quota || 50 * 1024 * 1024), // 1GB or device limit
    wasmSupport: typeof WebAssembly !== 'undefined',
    sharedArrayBufferSupport: typeof SharedArrayBuffer !== 'undefined',
    webglSupport: !!document.createElement('canvas').getContext('webgl2'),
    webWorkerSupport: typeof Worker !== 'undefined',
    webSocketSupport: 'WebSocket' in self,
    maxDuration: 60000, // 60 seconds per job
    costPerJob: 0.0 // FREE!
  };
}

// ============================================================================
// CLIENT-SIDE: Job submission and result collection
// ============================================================================

class PacketFSBrowserCompute {
  constructor(serviceWorkerUrl = '/packetfs-sw.js') {
    this.serviceWorkerUrl = serviceWorkerUrl;
    this.registration = null;
    this.workerChannel = null;
    this.jobResults = new Map();
    this.metrics = {
      jobsExecuted: 0,
      totalBytesProcessed: 0,
      totalExecutionTimeMs: 0,
      successRate: 0
    };
  }

  /**
   * Initialize browser compute runtime
   */
  async initialize() {
    try {
      if (!('serviceWorker' in navigator)) {
        throw new Error('Service Workers not supported');
      }
      
      // Register service worker
      this.registration = await navigator.serviceWorker.register(this.serviceWorkerUrl, {
        scope: '/'
      });
      
      console.log('[PFS Browser] Service Worker registered:', this.registration);
      
      // Set up communication channel
      this.workerChannel = new MessageChannel();
      
      const controller = navigator.serviceWorker.controller;
      if (controller) {
        controller.postMessage({ type: 'init', port: this.workerChannel.port2 }, [this.workerChannel.port2]);
      }
      
      // Listen for results from service worker
      this.workerChannel.port1.onmessage = (event) => {
        this.handleWorkerMessage(event.data);
      };
      
      return true;
    } catch (error) {
      console.error('[PFS Browser] Initialization failed:', error);
      return false;
    }
  }

  /**
   * Submit a PacketFS job for execution
   */
  async submitJob(program, options = {}) {
    const jobId = `job-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    try {
      // Use Fetch API to send to service worker
      const response = await fetch('/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jobId,
          program,
          timeout: options.timeout || 30000
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        this.jobResults.set(jobId, result);
        this.recordMetrics(result);
        return {
          jobId,
          success: true,
          result: result.results,
          executionTimeMs: result.executionTimeMs,
          bytesProcessed: result.bytesProcessed
        };
      } else {
        return {
          jobId,
          success: false,
          error: result.error
        };
      }
    } catch (error) {
      return {
        jobId,
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Handle message from service worker
   */
  handleWorkerMessage(message) {
    if (message.type === 'result') {
      this.jobResults.set(message.jobId, message.data);
      this.recordMetrics({
        executionTimeMs: message.executionTimeMs,
        bytesProcessed: message.bytesProcessed,
        success: message.success
      });
    }
  }

  /**
   * Record execution metrics
   */
  recordMetrics(result) {
    this.metrics.jobsExecuted++;
    this.metrics.totalBytesProcessed += result.bytesProcessed || 0;
    this.metrics.totalExecutionTimeMs += result.executionTimeMs || 0;
    
    if (result.success) {
      this.metrics.successRate = (this.metrics.successRate * (this.metrics.jobsExecuted - 1) + 1) / this.metrics.jobsExecuted;
    }
  }

  /**
   * Get job result
   */
  getResult(jobId) {
    return this.jobResults.get(jobId);
  }

  /**
   * Get metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      avgExecutionTimeMs: this.metrics.totalExecutionTimeMs / Math.max(1, this.metrics.jobsExecuted),
      avgBytesPerJob: this.metrics.totalBytesProcessed / Math.max(1, this.metrics.jobsExecuted)
    };
  }

  /**
   * Connect to PacketFS coordinator
   */
  async connectToCoordinator(coordinatorUrl = COORDINATOR_URL) {
    return new Promise((resolve, reject) => {
      try {
        const ws = new WebSocket(coordinatorUrl);
        
        ws.onopen = () => {
          console.log('[PFS Browser] Connected to coordinator');
          
          // Register this browser as a compute node
          ws.send(JSON.stringify({
            type: 'register',
            capabilities: this.getBrowserCapabilities(),
            metrics: this.getMetrics()
          }));
          
          resolve(ws);
        };
        
        ws.onmessage = (event) => {
          const message = JSON.parse(event.data);
          
          if (message.type === 'job') {
            // Receive job from coordinator
            this.submitJob(message.program, { timeout: message.timeout });
          }
        };
        
        ws.onerror = (error) => {
          console.error('[PFS Browser] Coordinator connection error:', error);
          reject(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Get browser capabilities
   */
  getBrowserCapabilities() {
    return {
      hardwareConcurrency: navigator.hardwareConcurrency || 4,
      deviceMemory: navigator.deviceMemory || 4,
      wasmSupport: typeof WebAssembly !== 'undefined',
      webglSupport: !!document.createElement('canvas').getContext('webgl2'),
      maxDuration: 60000,
      costPerJob: 0.0 // FREE!
    };
  }
}

// Auto-initialize when page loads (if needed)
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    // Only initialize if explicitly requested
    if (window.PACKETFS_AUTO_INIT) {
      const compute = new PacketFSBrowserCompute();
      compute.initialize().then(() => {
        window.packetfsCompute = compute;
        console.log('[PFS] Browser compute ready!');
      });
    }
  });
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { PacketFSBrowserCompute };
}
