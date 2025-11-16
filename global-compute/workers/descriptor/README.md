# PacketFS Descriptor Worker (Cloudflare)

This Worker serves content-addressed PacketFS descriptors from an R2 bucket (and an optional static origin fallback) and caches them at the edge.

Endpoints:
- GET /v1/desc/<hash>: returns descriptor blob (e.g., CBOR/JSON) by content hash
- GET /health: health info (colo, bindings)

Bindings:
- R2 bucket: DESC_BUCKET (set in wrangler.toml)
- Optional env var: STATIC_ORIGIN (e.g., https://static.example.com)

Cache:
- Uses Cache API and Cache-Control: public, max-age=31536000, immutable
- ETag set to <hash>

Quick start:
1) Install Wrangler: npm i -g wrangler (or use npx wrangler)
2) Create an R2 bucket in your Cloudflare account (e.g., pfs-descriptors)
3) Update wrangler.toml bucket_name to match
4) Publish:
   cd workers/descriptor
   wrangler publish

Dev:
- wrangler dev --local (no R2); for R2 in dev, use "wrangler dev" with proper account binding.

Upload descriptors:
- You can upload descriptors to R2 via the dashboard or API, key = <hash>, content-type = application/cbor or application/json.
- Optionally, set STATIC_ORIGIN to a static host serving /v1/desc/<hash> paths; Worker will backfill R2 on cache misses.
