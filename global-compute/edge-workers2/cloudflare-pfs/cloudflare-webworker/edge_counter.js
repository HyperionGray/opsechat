// Edge Counter - Count unique Cloudflare edges we can access
// Each edge reports in, we track unique locations in KV

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // GET /count - Report this edge and return total count
    if (path === '/count') {
      const edge = request.cf?.colo || 'unknown';
      const timestamp = Date.now();
      
      // Store this edge's heartbeat in KV
      const key = `edge:${edge}`;
      await env.PCPU_STATE.put(key, JSON.stringify({
        edge,
        timestamp,
        last_seen: new Date().toISOString(),
      }), {
        expirationTtl: 3600, // Expire after 1 hour
      });

      // Count all active edges
      const list = await env.PCPU_STATE.list({ prefix: 'edge:' });
      const edges = list.keys.map(k => k.name.replace('edge:', ''));

      return new Response(JSON.stringify({
        your_edge: edge,
        total_edges: edges.length,
        all_edges: edges.sort(),
        timestamp: new Date().toISOString(),
        message: `📍 You are at ${edge}. We have ${edges.length} active edges!`,
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // GET /edges - List all active edges
    if (path === '/edges') {
      const list = await env.PCPU_STATE.list({ prefix: 'edge:' });
      const edges = await Promise.all(
        list.keys.map(async (k) => {
          const data = await env.PCPU_STATE.get(k.name);
          return JSON.parse(data);
        })
      );

      return new Response(JSON.stringify({
        total: edges.length,
        edges: edges.sort((a, b) => a.edge.localeCompare(b.edge)),
      }, null, 2), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // GET /reset - Clear all edge counts
    if (path === '/reset') {
      const list = await env.PCPU_STATE.list({ prefix: 'edge:' });
      await Promise.all(
        list.keys.map(k => env.PCPU_STATE.delete(k.name))
      );

      return new Response(JSON.stringify({
        message: 'All edge counts cleared!',
        deleted: list.keys.length,
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Default: instructions
    return new Response(`
🌊 PacketFS Edge Counter 🔥

Endpoints:
  GET /count  - Report your edge location and see total
  GET /edges  - List all active edges
  GET /reset  - Clear all counts

Usage:
  # Count from your location
  curl https://your-worker.workers.dev/count

  # See all edges
  curl https://your-worker.workers.dev/edges

Try hitting /count from multiple locations to see different edges!
    `, {
      headers: { 'Content-Type': 'text/plain' }
    });
  }
};
