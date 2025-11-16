#!/bin/bash
set -euo pipefail

# PacketFS Tailnet Deployment Script
# ONE COMMAND to deploy to your Tailnet!

echo "🚀 PacketFS Unified Compute - Tailnet Deployment"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check prerequisites
echo -e "${BLUE}[1/6] Checking prerequisites...${NC}"

if ! command -v tailscale &> /dev/null; then
    echo "❌ Tailscale not installed. Install with:"
    echo "   curl -fsSL https://tailscale.com/install.sh | sh"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed. Install with:"
    echo "   curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not installed"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# 2. Ensure Tailscale is connected
echo -e "${BLUE}[2/6] Verifying Tailscale connection...${NC}"

if ! tailscale status | grep -q "connected"; then
    echo "❌ Tailscale not connected. Run:"
    echo "   tailscale up"
    exit 1
fi

TAILNET_NAME=$(tailscale status | grep "Hostname\|Base" | head -1 | awk '{print $2}')
echo -e "${GREEN}✓ Connected to Tailnet: ${TAILNET_NAME}${NC}"
echo ""

# 3. Set up Python environment
echo -e "${BLUE}[3/6] Setting up Python environment...${NC}"

cd /home/punk/Projects/packetfs/unified-compute

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo -e "${GREEN}✓ Python environment ready${NC}"
echo ""

# 4. Start Redis
echo -e "${BLUE}[4/6] Starting Redis...${NC}"

if ! docker ps | grep -q redis; then
    docker run -d -p 6379:6379 --name packetfs-redis redis:alpine > /dev/null 2>&1
    sleep 2
fi

echo -e "${GREEN}✓ Redis running at redis://localhost:6379${NC}"
echo ""

# 5. Get Tailnet IP
echo -e "${BLUE}[5/6] Getting Tailnet IP...${NC}"

TAILNET_IP=$(tailscale ip -4)
echo -e "${GREEN}✓ Dispatcher will be at: http://${TAILNET_IP}:8080${NC}"
echo ""

# 6. Start dispatcher
echo -e "${BLUE}[6/6] Starting dispatcher...${NC}"

# Create systemd service if root
if [ "$EUID" -eq 0 ]; then
    cat > /etc/systemd/system/packetfs-dispatcher.service << EOF
[Unit]
Description=PacketFS Unified Compute Dispatcher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/punk/Projects/packetfs/unified-compute
ExecStart=/home/punk/Projects/packetfs/unified-compute/venv/bin/python3 dispatcher.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
Environment="REDIS_URL=redis://localhost:6379"

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl start packetfs-dispatcher
    systemctl enable packetfs-dispatcher
    echo -e "${GREEN}✓ Dispatcher service started${NC}"
else
    # Run in background
    nohup python3 dispatcher.py --host 0.0.0.0 --port 8080 > /tmp/packetfs-dispatcher.log 2>&1 &
    sleep 2
    echo -e "${GREEN}✓ Dispatcher running (PID: $!)${NC}"
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✓ DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# 7. Verification
echo -e "${YELLOW}Verifying setup...${NC}"

if curl -s http://${TAILNET_IP}:8080/health > /dev/null; then
    echo -e "${GREEN}✓ Dispatcher is responsive${NC}"
else
    echo -e "${YELLOW}⚠ Dispatcher may be starting, give it a moment...${NC}"
    sleep 3
fi

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "1. Test locally:"
echo "   curl http://${TAILNET_IP}:8080/health"
echo ""
echo "2. Deploy compute nodes:"
echo "   # Get auth key"
echo "   export TAILSCALE_AUTH_KEY=\$(tailscale authkey create --reusable --preauthorized)"
echo ""
echo "   # Launch EC2 instance with Tailscale"
echo "   aws ec2 run-instances \\"
echo "     --image-ids ami-0c55b159cbfafe1f0 \\"
echo "     --instance-type t3.micro \\"
echo "     --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=packetfs-compute-1}]'"
echo ""
echo "3. SSH into instance and run:"
echo "   curl -fsSL https://tailscale.com/install.sh | sh"
echo "   sudo tailscale up --authkey=\$TAILSCALE_AUTH_KEY"
echo "   git clone https://github.com/your-repo/packetfs.git"
echo "   cd packetfs/unified-compute"
echo "   pip3 install -r requirements.txt"
echo "   python3 dispatcher.py --host 0.0.0.0 --port 8080"
echo ""
echo "4. Monitor your Tailnet:"
echo "   tailscale status | grep packetfs"
echo ""
echo -e "${GREEN}🚀 Your PacketFS cluster is online and ready!${NC}"
