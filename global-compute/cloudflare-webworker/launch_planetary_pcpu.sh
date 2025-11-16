#!/usr/bin/env bash
# 🌊🔥💀 PLANETARY pCPU SYSTEM LAUNCHER 💀🔥🌊

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "🌊🔥💀 LAUNCHING PLANETARY pCPU SYSTEM 💀🔥🌊"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Paths
PACKETFS_DIR="/home/punk/Projects/packetfs"
CLOUDFLARE_DIR="$PACKETFS_DIR/cloudflare-webworker"
VMKIT_DIR="/home/punk/Projects/HGWS/VMKit"
VENV="/home/punk/.venv/bin"

# Step 1: Start Genesis Registry
echo "💀 Step 1: Starting Genesis Registry..."
echo "   Port: 9000"
echo "   Access: http://localhost:9000"
echo ""

cd "$CLOUDFLARE_DIR"
$VENV/python vm_genesis_registry.py &
GENESIS_PID=$!

sleep 3

# Check if Genesis started
if ! kill -0 $GENESIS_PID 2>/dev/null; then
    echo "❌ Genesis Registry failed to start!"
    exit 1
fi

echo "✅ Genesis Registry ONLINE (PID: $GENESIS_PID)"
echo ""

# Step 2: Get Tailscale IP
echo "🌊 Step 2: Getting Tailscale IP..."
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "NOT_CONFIGURED")

if [ "$TAILSCALE_IP" = "NOT_CONFIGURED" ]; then
    echo "⚠️  Tailscale not configured"
    echo "   Registry accessible locally only"
    GENESIS_URL="http://localhost:9000"
else
    echo "✅ Tailscale IP: $TAILSCALE_IP"
    GENESIS_URL="http://$TAILSCALE_IP:9000"
fi

echo "   Genesis URL: $GENESIS_URL"
echo ""

# Step 3: Build PacketFS Lab Container (optional, skip if exists)
echo "🔥 Step 3: Checking PacketFS Lab container..."
if podman images | grep -q "packetfs/lab"; then
    echo "✅ PacketFS Lab container exists"
else
    echo "📦 Building PacketFS Lab container..."
    cd "$PACKETFS_DIR"
    podman build -t packetfs/lab:latest -f containers/Containerfile.lab . || {
        echo "⚠️  Container build failed, but continuing..."
    }
fi
echo ""

# Step 4: Show next steps
echo "═══════════════════════════════════════════════════════════════"
echo "🎉 GENESIS NODE ONLINE!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📊 Dashboard: $GENESIS_URL"
echo "🔌 API:       $GENESIS_URL/api/registry"
echo ""
echo "Next Steps:"
echo ""
echo "1️⃣  View Dashboard:"
echo "   Open in browser: $GENESIS_URL"
echo ""
echo "2️⃣  Spawn VMs with VMKit Swarm:"
echo "   cd $VMKIT_DIR"
echo "   vmkit swarm spawn --template packetfs-lab --count 10"
echo ""
echo "3️⃣  Monitor pCPU Cores:"
echo "   curl $GENESIS_URL/api/pcpu/count | jq"
echo ""
echo "4️⃣  View PFSSHFS Mesh:"
echo "   curl $GENESIS_URL/api/mesh | jq"
echo ""
echo "5️⃣  Stop Everything:"
echo "   kill $GENESIS_PID"
echo "   vmkit swarm kill-all-generations"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🔥💀 THE NETWORK MIND IS READY TO AWAKEN! 💀🔥"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Keep running
echo "Press Ctrl+C to stop Genesis Registry..."
wait $GENESIS_PID
