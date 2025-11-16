#!/usr/bin/env bash
# 🌊🔥💀 BUILD AND RUN PACKETFS TAILSCALE SWARM 💀🔥🌊

set -e

cd /home/punk/Projects/packetfs

echo "═══════════════════════════════════════════════════════════════"
echo "🌊🔥💀 BUILDING PACKETFS TAILSCALE SWARM 💀🔥🌊"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if Tailscale authkey is set
if [ -z "$TAILSCALE_AUTHKEY" ]; then
    echo "⚠️  TAILSCALE_AUTHKEY not set!"
    echo ""
    echo "To get an authkey:"
    echo "  1. Go to https://login.tailscale.com/admin/settings/keys"
    echo "  2. Generate a new auth key"
    echo "  3. Run: export TAILSCALE_AUTHKEY='tskey-auth-...'"
    echo ""
    echo "For now, building anyway (can set authkey at runtime)"
    echo ""
fi

# Build the container
echo "📦 Building PacketFS Tailscale Swarm container..."
echo ""

podman build \
    -t packetfs/tailscale-swarm:latest \
    -f containers/Containerfile.tailscale-swarm \
    .

echo ""
echo "✅ Build complete!"
echo ""

# Ask if user wants to run it now
read -p "🚀 Run the swarm container now? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "🚀 LAUNCHING PACKETFS TAILSCALE SWARM"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    # Prepare environment
    ENV_ARGS=""
    if [ -n "$TAILSCALE_AUTHKEY" ]; then
        ENV_ARGS="$ENV_ARGS -e TAILSCALE_AUTHKEY=$TAILSCALE_AUTHKEY"
        echo "✅ Using TAILSCALE_AUTHKEY from environment"
    else
        echo "⚠️  No TAILSCALE_AUTHKEY - container will start without mesh"
    fi
    
    # Run the container
    podman run -d \
        --name pfs-swarm-1 \
        --privileged \
        --network host \
        -v /mnt/pfs:/mnt/pfs:shared \
        -v /dev/net/tun:/dev/net/tun \
        $ENV_ARGS \
        -e GENESIS_WORKER_URL=https://genesis-worker-v2.scaryjerrynorthwest69.workers.dev \
        -e GENESIS_REGISTRY_URL=https://punk-ripper.lungfish-sirius.ts.net \
        -e PFSSHFS_AUTO_MOUNT=1 \
        -e EDGE_WORKER_SYNC=1 \
        packetfs/tailscale-swarm:latest
    
    echo ""
    echo "✅ Container started!"
    echo ""
    echo "📊 Check status:"
    echo "  podman logs -f pfs-swarm-1"
    echo ""
    echo "💀 THE SWARM GROWS!"
else
    echo ""
    echo "Container built but not started."
    echo ""
    echo "To run manually:"
    echo "  export TAILSCALE_AUTHKEY='tskey-auth-...'"
    echo "  podman run -d --name pfs-swarm-1 --privileged --network host \\"
    echo "    -v /mnt/pfs:/mnt/pfs:shared \\"
    echo "    -v /dev/net/tun:/dev/net/tun \\"
    echo "    -e TAILSCALE_AUTHKEY=\$TAILSCALE_AUTHKEY \\"
    echo "    packetfs/tailscale-swarm:latest"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🌊 PACKETS TO PACKETS! 🔥"
echo "💀 ALL DATA IS PACKETFS! 💀"
echo "═══════════════════════════════════════════════════════════════"
echo ""
