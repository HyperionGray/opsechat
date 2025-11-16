#!/bin/bash
# PacketFS Translator CDN Deployment
# 🌊 Deploy to 300+ Cloudflare edge locations! 🔥

set -e

echo "=============================================="
echo "  PacketFS Translator CDN Deployment"
echo "  🌊 VIRAL SPREAD BEGINS HERE 🔥"
echo "=============================================="
echo ""

# Check for wrangler
if ! command -v wrangler &> /dev/null; then
    echo "❌ wrangler not found!"
    echo "Install: npm install -g wrangler"
    exit 1
fi

echo "✅ wrangler found"
echo ""

# Step 1: Create R2 buckets
echo "📦 Creating R2 buckets..."
wrangler r2 bucket create pfs-descriptors 2>/dev/null || echo "  (pfs-descriptors already exists)"
wrangler r2 bucket create pfs-translators 2>/dev/null || echo "  (pfs-translators already exists)"
echo "✅ R2 buckets ready"
echo ""

# Step 2: Deploy worker
echo "🚀 Deploying worker to Cloudflare..."
wrangler deploy
echo "✅ Worker deployed!"
echo ""

# Step 3: Show endpoints
echo "=============================================="
echo "  DEPLOYMENT COMPLETE! 🎉"
echo "=============================================="
echo ""
echo "Your worker is now live at:"
echo "  https://packetfs-translator-cdn.<your-subdomain>.workers.dev"
echo ""
echo "Endpoints:"
echo "  GET /health              - Worker status"
echo "  GET /v1/translator/info  - Translator VM metadata"
echo "  GET /bootstrap           - Download page"
echo "  GET /v1/translator       - Download translator VM"
echo ""
echo "Next steps:"
echo "  1. Build the 50KB translator VM"
echo "  2. Upload: wrangler r2 object put pfs-translators/translator-v1-iprog.vm --file translator.vm"
echo "  3. Share /bootstrap URL → Viral spread begins! 🌊"
echo ""
echo "THE PACKETS WILL DECIDE! 💎"
echo "=============================================="
