# Edge Workers

**Roles**
- Distribution (cache images/artifacts).
- Control/API proxy to genesis (via Tunnel).
- Job edge: submit/lease/result/status.

**Artifacts in repo**
- `genesis_worker.js` – auto-register edges, dashboards, heartbeats.
- `collision_finder.js` – distributed demo worker.
- `wrangler-genesis.toml` – wrangler config/bindings.

**TODO**
- [ ] Add `/pcpu/jobs/*` endpoints (KV-backed or DO-backed).
- [ ] Smart Placement toggles per route.
- [ ] Access policies for private origins via Tunnel.
