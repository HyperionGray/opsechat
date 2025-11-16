# Cloudflare integration workspace

This directory holds Cloudflare-related assets for development use inside the
packetfs-cloudflare dev container.

- Place your Workers project(s) here (wrangler.toml, src/, etc.)
- Use a secrets env file at ../../secrets/cloudflare.env (copied from the
  provided cloudflare.env.example) to provide CLOUDFLARE_API_TOKEN without
  exposing it in plaintext.
- Inside the dev container, Wrangler is preinstalled globally.

Quickstart (after the dev pod is running):

- Exec into the container:
  podman exec -it packetfs-cloudflare bash

- Authenticate (if needed):
  wrangler login  # or rely on CLOUDFLARE_API_TOKEN in env

- Deploy a worker from /opt/cloudflare/<project>:
  cd /opt/cloudflare/my-worker
  wrangler deploy
