# Swarm

**Pieces**
- **Genesis Registry** – VM/peer DB, heartbeats, mesh topology.
- **Agents** – join, mount PFSSHFS, report, replicate if allowed.
- **Infrastructure scripts** – move/launch helpers now under `hgws/vmkit/swarm-infra/scripts`.
- **Images** – OSv (Capstan) and cloud-init images.

**Immediate TODOs**
- [ ] Define generation/fan-out caps globally & per-tenant.
- [ ] Image distribution via Workers cache.
- [ ] Health checks & safe drains.
