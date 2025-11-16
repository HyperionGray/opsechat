#!/usr/bin/env bash
# Setup Cloudflare environment for wrangler commands

# Export CF_TOKEN as CLOUDFLARE_API_TOKEN (wrangler's preferred name)
export CLOUDFLARE_API_TOKEN="${CF_TOKEN}"
export CLOUDFLARE_ACCOUNT_ID="fb5c0c53befadedfd04c42062262c45e"

echo "✅ Cloudflare environment configured"
echo "   Account ID: ${CLOUDFLARE_ACCOUNT_ID}"
echo "   API Token: $(echo ${CLOUDFLARE_API_TOKEN} | cut -c1-10)..."
echo ""
echo "Run wrangler commands directly now, or:"
echo "  source scripts/cf/setup_env.sh"
echo "  npx wrangler whoami"
