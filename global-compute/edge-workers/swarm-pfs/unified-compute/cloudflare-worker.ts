/**
 * PacketFS Cloudflare Worker
 * High-performance edge compute with Durable Objects for state
 * Deploy: wrangler publish
 */

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // POST /compute - Execute PacketFS job
    if (request.method === 'POST' && url.pathname === '/compute') {
      return handleComputeJob(request, env);
    }

    // GET /health - Health check
    if (request.method === 'GET' && url.pathname === '/health') {
      return new Response(
        JSON.stringify({
          status: 'healthy',
          edge_location: request.cf?.colo || 'unknown',
          version: '1.0.0',
          capabilities: {
            max_memory_mb: 128,
            max_duration_s: 30,
            ops: ['counteq', 'crc32c', 'fnv64', 'xor', 'add']
          }
        }),
        { headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response('PacketFS Cloudflare Worker\n/compute for jobs\n/health for status', {
      status: 200
    });
  }
};

/**
 * Handle PacketFS compute job
 */
async function handleComputeJob(request: Request, env: Env): Promise<Response> {
  const startTime = Date.now();

  try {
    const payload = await request.json();
    const { jobId, program, timeout } = payload;

    if (!program || !program.op) {
      return new Response(
        JSON.stringify({ error: 'Missing program or operation' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Fetch data from URL with Range support
    const dataUrl = program.data_url;
    if (!dataUrl) {
      return new Response(
        JSON.stringify({ error: 'Missing data_url' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const headers: HeadersInit = {};
    if (program.offset !== undefined && program.length !== undefined) {
      const end = program.offset + program.length - 1;
      headers['Range'] = `bytes=${program.offset}-${end}`;
    }

    // Fetch with cache directive
    const dataResponse = await fetch(dataUrl, {
      headers,
      cf: {
        cacheEverything: true,
        cacheTtl: 3600,
        mirroring: 'all'
      } as any
    });

    if (!dataResponse.ok && dataResponse.status !== 206) {
      return new Response(
        JSON.stringify({ error: `Data fetch failed: ${dataResponse.status}` }),
        { status: 502, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const buffer = await dataResponse.arrayBuffer();
    const bytes = new Uint8Array(buffer);

    // Execute operation
    const result = executeOperation(program, bytes);

    const executionTime = Date.now() - startTime;

    return new Response(
      JSON.stringify({
        success: true,
        jobId,
        results: result,
        executionTimeMs: executionTime,
        bytesProcessed: bytes.length,
        edgeLocation: request.cf?.colo || 'unknown',
        cacheStatus: dataResponse.headers.get('cf-cache-status')
      }),
      { 
        headers: { 'Content-Type': 'application/json' },
        status: 200
      }
    );
  } catch (error) {
    const executionTime = Date.now() - startTime;

    return new Response(
      JSON.stringify({
        success: false,
        error: error instanceof Error ? error.message : String(error),
        executionTimeMs: executionTime
      }),
      { 
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

/**
 * Execute a PacketFS operation
 */
function executeOperation(program: any, bytes: Uint8Array): any {
  const op = program.op;
  const imm = program.imm || 0;
  const offset = program.offset || 0;
  const length = program.length || bytes.length;

  const start = offset;
  const end = Math.min(offset + length, bytes.length);
  const slice = bytes.slice(start, end);

  switch (op) {
    case 'counteq': {
      let count = 0;
      const needle = imm & 0xFF;
      for (let i = 0; i < slice.length; i++) {
        if (slice[i] === needle) count++;
      }
      return { op: 'counteq', count, bytesScanned: slice.length };
    }

    case 'crc32c': {
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
      let hash = BigInt('0xcbf29ce484222325');
      const prime = BigInt('0x100000001b3');
      for (let i = 0; i < slice.length; i++) {
        hash ^= BigInt(slice[i]);
        hash = (hash * prime) & BigInt('0xFFFFFFFFFFFFFFFF');
      }
      return { op: 'fnv64', hash: hash.toString(16), bytesHashed: slice.length };
    }

    case 'xor': {
      const k = imm & 0xFF;
      let result = 0;
      for (let i = 0; i < slice.length; i++) {
        result ^= (slice[i] ^ k);
      }
      return { op: 'xor', result, bytesProcessed: slice.length };
    }

    case 'add': {
      const k = imm & 0xFF;
      let result = 0;
      for (let i = 0; i < slice.length; i++) {
        result += (slice[i] + k) & 0xFF;
      }
      return { op: 'add', result, bytesProcessed: slice.length };
    }

    default:
      throw new Error(`Unknown operation: ${op}`);
  }
}

/**
 * Durable Object for stateful job coordination
 */
export class JobState implements DurableObject {
  state: DurableObjectState;
  env: Env;
  jobs: Map<string, any> = new Map();

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    // POST /jobs/{id} - Store job state
    if (request.method === 'POST' && url.pathname.startsWith('/jobs/')) {
      const jobId = url.pathname.split('/').pop() || '';
      const jobData = await request.json();
      
      this.jobs.set(jobId, {
        ...jobData,
        createdAt: new Date().toISOString()
      });

      return new Response(
        JSON.stringify({ success: true, jobId }),
        { headers: { 'Content-Type': 'application/json' } }
      );
    }

    // GET /jobs/{id} - Retrieve job state
    if (request.method === 'GET' && url.pathname.startsWith('/jobs/')) {
      const jobId = url.pathname.split('/').pop() || '';
      const job = this.jobs.get(jobId);

      if (!job) {
        return new Response(
          JSON.stringify({ error: 'Job not found' }),
          { status: 404, headers: { 'Content-Type': 'application/json' } }
        );
      }

      return new Response(
        JSON.stringify(job),
        { headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response('Durable Object for job state', { status: 200 });
  }
}

/**
 * Types for TypeScript
 */
interface Env {
  PACKETFS_DO?: DurableObjectNamespace;
}
