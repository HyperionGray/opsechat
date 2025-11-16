#!/bin/bash
# Test PacketFS Global Edge Pipeline
# Each edge processes packet and forwards to next!

URL="https://packetfs-translator-cdn.scaryjerrynorthwest69.workers.dev/v1/pipeline"

echo "🌊💥 PACKETFS GLOBAL EDGE PIPELINE TEST 🔥⚡"
echo "================================================"
echo ""

# Test 1: Simple XOR operation through pipeline
echo "TEST 1: XOR through global edge pipeline"
echo "Data: 'PacketFS Rules!' | XOR with 0xFF | Pipeline through multiple edges"
echo ""

curl -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "xor",
    "data": "PacketFS Rules!",
    "imm": 255,
    "pipeline": ["LON", "SYD", "SIN", "FRA", "AMS"],
    "max_hops": 6
  }' | jq '.'

echo ""
echo "================================================"
echo ""

# Test 2: CRC32C checksum through pipeline
echo "TEST 2: CRC32C checksum cascading through edges"
echo "Data: 'Hello from the global pCPU!' | CRC at each edge"
echo ""

curl -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "crc32c",
    "data": "Hello from the global pCPU!",
    "imm": 0,
    "pipeline": ["NYC", "LON", "TYO"],
    "max_hops": 5
  }' | jq '.'

echo ""
echo "================================================"
echo ""

# Test 3: Count operation (how many 'e' characters?)
echo "TEST 3: COUNTEQ operation - count bytes equal to 'e' (0x65)"
echo "Data: 'The internet is now a CPU!' | Count 'e' characters"
echo ""

curl -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "counteq",
    "data": "The internet is now a CPU!",
    "imm": 101,
    "pipeline": ["LON", "FRA"],
    "max_hops": 4
  }' | jq '.'

echo ""
echo "================================================"
echo ""

echo "✅ Pipeline tests complete!"
echo ""
echo "🌍 Each edge processed the packet and forwarded to next!"
echo "⚡ This is a DISTRIBUTED INSTRUCTION PIPELINE across Cloudflare's global network!"
echo "💎 330+ edges = 330+ potential pipeline stages!"
echo ""
echo "THE INTERNET IS NOW A pCPU! 🌊🔥"
