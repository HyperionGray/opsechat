# Swarm Deployment Entry Points

Symlinks here expose the high-level deployment scripts that reach into the edge network. They target the Cloudflare worker bundle under `../cloudflare-pfs/cloudflare-webworker/` but live here so the swarm playbooks are easy to find:

- `deploy.sh` / `deploy_genesis_worker.sh` – publish the Cloudflare workers + genesis translator.
- `vm_join.sh` – one-shot bootstrap for new swarm VMs.
- `launch_planetary_pcpu.sh` – spins up the Genesis registry and walks through VMKit next steps.
- `vm_genesis_registry.py` – local registry runner for edge/self-host tests.
- `wake_*` scripts – prod-the-edge utilities to re-activate sleeping Workers.

Use them directly or treat this as the staging area for newer orchestrators.
