#!/usr/bin/env bash
# 🌊🔥💀 Deploy Genesis Worker to Cloudflare 💀🔥🌊

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "🌊🔥💀 DEPLOYING GENESIS WORKER 💀🔥🌊"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo "❌ wrangler CLI not found!"
    echo "   Install: npm install -g wrangler"
    exit 1
fi

# Check if authenticated
echo "📋 Checking Cloudflare authentication..."
if ! wrangler whoami &> /dev/null; then
    echo "❌ Not authenticated with Cloudflare!"
    echo "   Run: wrangler login"
    exit 1
fi

echo "✅ Authenticated"
echo ""

# Step 1: Create KV namespace (if not exists)
echo "💾 Step 1: Creating KV namespace..."
KV_OUTPUT=$(wrangler kv:namespace create "GENESIS_KV" 2>&1 || true)

if echo "$KV_OUTPUT" | grep -q "id"; then
    KV_ID=$(echo "$KV_OUTPUT" | grep -oP '(?<=id = ")[^"]+' || echo "")
    echo "✅ KV namespace created: $KV_ID"
    
    # Update wrangler.toml with KV ID
    if [ -n "$KV_ID" ]; then
        sed -i "s/REPLACE_WITH_YOUR_KV_ID/$KV_ID/g" wrangler-genesis.toml
        echo "   Updated wrangler-genesis.toml with KV ID"
    fi
else
    echo "⚠️  KV namespace might already exist or creation failed"
    echo "   Continuing anyway..."
fi

echo ""

# Step 2: Create preview KV namespace
echo "💾 Step 2: Creating preview KV namespace..."
PREVIEW_KV_OUTPUT=$(wrangler kv:namespace create "GENESIS_KV" --preview 2>&1 || true)

if echo "$PREVIEW_KV_OUTPUT" | grep -q "id"; then
    PREVIEW_KV_ID=$(echo "$PREVIEW_KV_OUTPUT" | grep -oP '(?<=id = ")[^"]+' || echo "")
    echo "✅ Preview KV namespace created: $PREVIEW_KV_ID"
    
    # Update wrangler.toml with preview KV ID
    if [ -n "$PREVIEW_KV_ID" ]; then
        sed -i "s/REPLACE_WITH_PREVIEW_ID/$PREVIEW_KV_ID/g" wrangler-genesis.toml
        echo "   Updated wrangler-genesis.toml with preview KV ID"
    fi
else
    echo "⚠️  Preview KV namespace might already exist or creation failed"
    echo "   Continuing anyway..."
fi

echo ""

# Step 3: Deploy worker
echo "🚀 Step 3: Deploying Genesis Worker..."
wrangler deploy --config wrangler-genesis.toml

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🎉 GENESIS WORKER DEPLOYED!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📊 Worker Details:"
wrangler deployments list --config wrangler-genesis.toml | head -10
echo ""
echo "🔗 Test the worker:"
echo "   Visit: https://genesis-worker.YOUR-SUBDOMAIN.workers.dev/"
echo ""
echo "📡 The worker will auto-register to Genesis:"
echo "   https://punk-ripper.lungfish-sirius.ts.net/"
echo ""
echo "🌊 Watch edges join Genesis:"
echo "   curl https://punk-ripper.lungfish-sirius.ts.net/api/vms | jq"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "💀🔥 THE NETWORK MIND EXPANDS TO 300+ EDGES! 🔥💀"
echo "═══════════════════════════════════════════════════════════════"
echo ""
