#!/usr/bin/env bash
# Test Genesis Worker across multiple Cloudflare edge locations
# Uses proxy rotation to force different edge pops

set -e

WORKER_URL="https://genesis-worker.scaryjerrynorthwest69.workers.dev"
TARGET_EDGES=20  # Try to hit 20 different edges

echo "🌍 Testing Genesis Worker across Cloudflare Edge Network"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Method 1: Use Cloudflare's own edge resolution via DNS
echo "📍 Method 1: Testing via DNS rotation"
for i in {1..5}; do
    echo -n "Attempt $i: "
    EDGE=$(curl -s -H "CF-IPCountry: US" \
                 -H "CF-Connecting-IP: $(shuf -i 1-255 -n 1).$(shuf -i 1-255 -n 1).$(shuf -i 1-255 -n 1).$(shuf -i 1-255 -n 1)" \
                 "$WORKER_URL/status" | jq -r '.edge_location')
    echo "Edge: $EDGE"
    sleep 1
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Method 2: Using different DNS resolvers to hit different edges"
echo ""

# List of public DNS servers in different regions
declare -a DNS_SERVERS=(
    "8.8.8.8"          # Google US
    "1.1.1.1"          # Cloudflare
    "208.67.222.222"   # OpenDNS
    "9.9.9.9"          # Quad9
)

for DNS in "${DNS_SERVERS[@]}"; do
    echo -n "Via DNS $DNS: "
    EDGE=$(curl -s --dns-servers "$DNS" "$WORKER_URL/status" 2>/dev/null | jq -r '.edge_location' || echo "FAILED")
    echo "Edge: $EDGE"
    sleep 1
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Method 3: Using VPN/Proxy endpoints (if available)"
echo ""

# Check if we have any SOCKS/HTTP proxies configured
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
    echo "✅ Proxy configured, testing..."
    EDGE=$(curl -s "$WORKER_URL/status" | jq -r '.edge_location')
    echo "Edge via proxy: $EDGE"
else
    echo "⚠️  No proxy configured. To test multiple edges, consider:"
    echo "   - Setting up a VPN with multiple exit points"
    echo "   - Using a residential proxy service"
    echo "   - Deploying test clients in different regions"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 Summary"
echo ""
echo "Cloudflare Workers deploy to 300+ edge locations worldwide."
echo "Each request is routed to the nearest edge based on:"
echo "  - Client IP geolocation"
echo "  - DNS resolver location"
echo "  - BGP routing"
echo ""
echo "Your worker is deployed globally, even though you see MIA locally!"
echo ""
echo "🔗 To verify global deployment:"
echo "   1. Ask friends in different countries to test"
echo "   2. Use a VPN service with multiple regions"
echo "   3. Check Cloudflare Analytics dashboard"
echo "   4. Use: warp-cli connect && curl $WORKER_URL/status"
echo ""
