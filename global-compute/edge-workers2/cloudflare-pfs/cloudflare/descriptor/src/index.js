export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname || "/";

    if (path === "/health") {
      const out = {
        status: "ok",
        edge: request.cf?.colo || "unknown",
        r2: !!env.DESC_BUCKET,
        static_origin: env.STATIC_ORIGIN || null
      };
      return json(out);
    }

    if (path === "/bench") {
      const q = url.searchParams;
      const op = (q.get("op") || "xor").toLowerCase();
      const count = Math.max(1, Math.min(50_000_000, parseInt(q.get("count") || "1000000", 10)));
      let x = 0 >>> 0;
      const t0 = Date.now();
      for (let i = 0; i < count; i++) {
        if (op === "add") x = (x + 1) >>> 0;
        else x = (x ^ 0xff) >>> 0; // xor imm8
      }
      const dt = (Date.now() - t0) / 1000.0;
      return json({ op, count, secs: dt, ops_per_sec: Math.floor(count / Math.max(dt, 1e-9)), junk: x });
    }

    const m = path.match(/^\/v1\/desc\/([A-Za-z0-9._-]+)$/);
    if (request.method === "GET" && m) {
      const hash = m[1];
      return await handleGetDescriptor(hash, request, env, ctx);
    }

    return new Response("ok", { status: 200 });
  }
}

async function handleGetDescriptor(hash, request, env, ctx) {
  const cacheKey = new Request(new URL(`/v1/desc/${hash}`, request.url).toString(), { method: "GET" });
  const cache = caches.default;
  let cached = await cache.match(cacheKey);
  if (cached) return cached;

  let obj = null;
  try {
    obj = await env.DESC_BUCKET.get(hash);
  } catch (_) {}

  if (obj) {
    const resp = objectToResponse(obj, hash);
    ctx.waitUntil(cache.put(cacheKey, resp.clone()));
    return resp;
  }

  const origin = env.STATIC_ORIGIN || "";
  if (origin) {
    const originUrl = new URL(`/v1/desc/${hash}`, origin);
    const oresp = await fetch(originUrl.toString(), { cf: { cacheEverything: true } });
    if (oresp.ok) {
      const body = await oresp.arrayBuffer();
      try {
        await env.DESC_BUCKET.put(hash, body, {
          httpMetadata: { contentType: oresp.headers.get("content-type") || "application/octet-stream" }
        });
      } catch (_) {}
      const resp = bufferToResponse(body, hash, oresp.headers.get("content-type"));
      ctx.waitUntil(cache.put(cacheKey, resp.clone()));
      return resp;
    }
  }

  return json({ error: "not found", hash }, 404);
}

function objectToResponse(obj, etag) {
  const headers = new Headers();
  headers.set("ETag", etag);
  headers.set("Cache-Control", "public, max-age=31536000, immutable");
  headers.set("Content-Type", obj.httpMetadata?.contentType || "application/octet-stream");
  return new Response(obj.body, { status: 200, headers });
}

function bufferToResponse(buf, etag, contentType) {
  const headers = new Headers();
  headers.set("ETag", etag);
  headers.set("Cache-Control", "public, max-age=31536000, immutable");
  headers.set("Content-Type", contentType || "application/octet-stream");
  return new Response(buf, { status: 200, headers });
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
