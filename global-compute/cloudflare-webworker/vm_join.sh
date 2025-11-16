#!/usr/bin/env bash
# 🌊🔥💀 VM JOIN SCRIPT 💀🔥🌊
#
# One-command to join the Planetary pCPU Swarm!
# Usage: curl https://genesis/vm_join.sh | bash

set -e

GENESIS_URL="${GENESIS_URL:-http://100.66.38.21:9000}"
VM_HOSTNAME=$(hostname)
VM_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -1)
VM_ID=$(cat /dev/urandom | tr -dc 'a-f0-9' | head -c 16)
PFSSHFS_ROOT="/mnt/pfs"

echo "═══════════════════════════════════════════════════════════════"
echo "🌊🔥💀 JOINING PLANETARY pCPU SWARM 💀🔥🌊"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "VM ID:       $VM_ID"
echo "Hostname:    $VM_HOSTNAME"
echo "IP:          $VM_IP"
echo "Genesis URL: $GENESIS_URL"
echo ""

# Step 1: Install dependencies
echo "📦 Step 1: Installing dependencies..."
apt-get update -qq
apt-get install -y -qq curl jq sshfs fuse3 openssh-server python3 2>/dev/null || true

# Step 2: Setup SSH for PFSSHFS
echo "🔐 Step 2: Setting up SSH..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Generate SSH key if not exists
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 2048 -f ~/.ssh/id_rsa -N "" -q
fi

# Enable SSH server
systemctl enable ssh 2>/dev/null || true
systemctl start ssh 2>/dev/null || true

# Step 3: Create pfsfs mount point
echo "💾 Step 3: Creating pfsfs mount..."
mkdir -p "$PFSSHFS_ROOT"
chmod 755 "$PFSSHFS_ROOT"

# Step 4: Register to Genesis
echo "📡 Step 4: Registering to Genesis Registry..."
REGISTER_DATA=$(cat <<EOF
{
  "vm_id": "$VM_ID",
  "hostname": "$VM_HOSTNAME",
  "ip": "$VM_IP",
  "ssh_port": 22,
  "pfsshfs_root": "$PFSSHFS_ROOT",
  "capabilities": ["pfsfs", "pcpu", "ssh"]
}
EOF
)

RESPONSE=$(curl -s -X POST "$GENESIS_URL/api/vm/register" \
  -H "Content-Type: application/json" \
  -d "$REGISTER_DATA")

if echo "$RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    echo "✅ Registered successfully!"
    
    # Get peer list
    PEERS=$(echo "$RESPONSE" | jq -r '.peers[]' 2>/dev/null || echo "")
    PEER_COUNT=$(echo "$PEERS" | wc -l)
    echo "   Found $PEER_COUNT peers in swarm"
else
    echo "❌ Registration failed: $RESPONSE"
    exit 1
fi

# Step 5: Mount PFSSHFS to all peers
echo "🌊 Step 5: Mounting PFSSHFS to peers..."
MOUNTED=0

# Get all VMs from Genesis
ALL_VMS=$(curl -s "$GENESIS_URL/api/vms" | jq -r '.vms | to_entries[] | "\(.key)|\(.value.ip)|\(.value.ssh_port)"')

while IFS='|' read -r peer_id peer_ip peer_port; do
    # Skip self
    if [ "$peer_id" = "$VM_ID" ]; then
        continue
    fi
    
    # Skip if already mounted
    if mountpoint -q "$PFSSHFS_ROOT/peer-$peer_id" 2>/dev/null; then
        continue
    fi
    
    echo "   Connecting to $peer_id ($peer_ip)..."
    
    # Create mount point
    mkdir -p "$PFSSHFS_ROOT/peer-$peer_id"
    
    # Add to known_hosts (auto-accept)
    ssh-keyscan -H -p "$peer_port" "$peer_ip" >> ~/.ssh/known_hosts 2>/dev/null || true
    
    # Try to mount (may fail if peer not ready, that's ok)
    if sshfs -o StrictHostKeyChecking=no,UserKnownHostsFile=/dev/null,allow_other \
            "root@$peer_ip:$PFSSHFS_ROOT" "$PFSSHFS_ROOT/peer-$peer_id" -p "$peer_port" 2>/dev/null; then
        
        # Report connection to Genesis
        curl -s -X POST "$GENESIS_URL/api/pfsshfs/connect" \
            -H "Content-Type: application/json" \
            -d "{\"source_vm\":\"$VM_ID\",\"target_vm\":\"$peer_id\"}" > /dev/null
        
        MOUNTED=$((MOUNTED + 1))
        echo "   ✅ Mounted $peer_id"
    else
        echo "   ⚠️  Could not mount $peer_id (may not be ready)"
        rmdir "$PFSSHFS_ROOT/peer-$peer_id" 2>/dev/null || true
    fi
done <<< "$ALL_VMS"

echo "   Mounted $MOUNTED peer filesystems"

# Step 6: Setup heartbeat service
echo "💓 Step 6: Setting up heartbeat..."
cat > /usr/local/bin/pfs-heartbeat.sh <<'HEARTBEAT_EOF'
#!/bin/bash
GENESIS_URL="${GENESIS_URL:-http://100.66.38.21:9000}"
VM_ID=$(cat /etc/pfs-vm-id)
PCPU_CORES=$(nproc)

# Get pfsshfs peers count
PEERS_COUNT=$(ls -1d /mnt/pfs/peer-* 2>/dev/null | wc -l)

# Get filesystem size
FS_SIZE_MB=$(df -BM /mnt/pfs | tail -1 | awk '{print $2}' | sed 's/M//')

# Send heartbeat
curl -s -X POST "$GENESIS_URL/api/vm/heartbeat" \
  -H "Content-Type: application/json" \
  -d "{
    \"vm_id\": \"$VM_ID\",
    \"pcpu_cores\": $PCPU_CORES,
    \"pfsshfs_peers\": $PEERS_COUNT,
    \"filesystem_size_mb\": $FS_SIZE_MB
  }" > /dev/null 2>&1
HEARTBEAT_EOF

chmod +x /usr/local/bin/pfs-heartbeat.sh
echo "$VM_ID" > /etc/pfs-vm-id

# Create systemd service for heartbeat
cat > /etc/systemd/system/pfs-heartbeat.service <<SYSTEMD_EOF
[Unit]
Description=PacketFS Genesis Heartbeat
After=network-online.target

[Service]
Type=oneshot
Environment="GENESIS_URL=$GENESIS_URL"
ExecStart=/usr/local/bin/pfs-heartbeat.sh

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

cat > /etc/systemd/system/pfs-heartbeat.timer <<TIMER_EOF
[Unit]
Description=PacketFS Genesis Heartbeat Timer

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s

[Install]
WantedBy=timers.target
TIMER_EOF

systemctl daemon-reload
systemctl enable pfs-heartbeat.timer
systemctl start pfs-heartbeat.timer

echo "✅ Heartbeat configured (every 30s)"

# Step 7: Final status
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🎉 SUCCESSFULLY JOINED SWARM!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "VM Details:"
echo "  ID:                $VM_ID"
echo "  Hostname:          $VM_HOSTNAME"
echo "  IP:                $VM_IP"
echo "  pCPU Cores:        $(nproc)"
echo "  PFSSHFS Root:      $PFSSHFS_ROOT"
echo "  Mounted Peers:     $MOUNTED"
echo ""
echo "Genesis Registry:    $GENESIS_URL"
echo "Dashboard:           $GENESIS_URL"
echo ""
echo "🌊🔥💀 THE NETWORK MIND GROWS! 💀🔥🌊"
echo ""
