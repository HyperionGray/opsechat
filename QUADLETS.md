# Podman Quadlets for Opsechat

This document describes how to deploy opsechat using Podman Quadlets for systemd integration. Quadlets provide a declarative way to manage containers as native systemd services.

## Overview

Quadlets allow you to define containers using simple configuration files that Podman automatically converts to systemd unit files. This provides:

- **Automatic startup** at boot
- **Service management** with systemctl
- **Logging** via journalctl
- **Health checks** and auto-restart
- **Dependency management** between containers

## Quick Start

### 1. Build the Container Image

First, build the opsechat container image (host networking avoids apt/DNS hiccups during build):

```bash
cd /path/to/opsechat
sudo podman build --runtime=runc --network host -t localhost/opsechat:latest .
```

### 2. Install Quadlet Files

Copy the quadlet files to the appropriate location:

**For user (rootless) deployment:**
```bash
mkdir -p ~/.config/containers/systemd/
cp quadlets/*.container ~/.config/containers/systemd/
cp quadlets/*.network ~/.config/containers/systemd/
cp quadlets/*.volume ~/.config/containers/systemd/
```

**For system-wide deployment (requires root):**
```bash
sudo mkdir -p /etc/containers/systemd/
sudo cp quadlets/*.container /etc/containers/systemd/
sudo cp quadlets/*.network /etc/containers/systemd/
sudo cp quadlets/*.volume /etc/containers/systemd/
```

### 3. Update Configuration Paths

Edit `~/.config/containers/systemd/opsechat-tor.container` and update the torrc path:

```ini
# Change this line to point to your actual torrc location:
Volume=/home/yourusername/opsechat/torrc:/etc/tor/torrc:ro
```

### 4. Reload and Start Services

**For user deployment:**
```bash
systemctl --user daemon-reload
systemctl --user start opsechat-app
```

**For system-wide deployment:**
```bash
sudo systemctl daemon-reload
sudo systemctl start opsechat-app
```

### 5. View Logs and Get Onion Address

```bash
# For user deployment:
journalctl --user -u opsechat-app -f

# For system-wide:
sudo journalctl -u opsechat-app -f
```

Look for the line: `Your service is available at: xxx.onion/xxx`

### 6. Enable Auto-Start at Boot

**For user deployment:**
```bash
systemctl --user enable opsechat-app
# Also enable lingering for the user (so services run without login)
loginctl enable-linger $USER
```

**For system-wide:**
```bash
sudo systemctl enable opsechat-app
```

## Quadlet Files

### opsechat.network

Defines the private bridge network for container communication.

```ini
[Network]
NetworkName=opsechat-network
Driver=bridge
```

### tor-data.volume

Persistent volume for Tor data (keys, cache, etc.).

```ini
[Volume]
VolumeName=tor-data
```

### opsechat-tor.container

Runs the Tor daemon with control port enabled.

Key settings:
- Installs Tor on Alpine Linux
- Mounts custom torrc configuration
- Exposes control port 9051 on the internal network
- Health checks verify the control port is ready

### opsechat-app.container

Runs the Flask application with all features.

Key settings:
- Connects to Tor via internal network
- No ports exposed to host (Tor-only access)
- Environment variables for Tor connection
- Depends on Tor container being healthy

## Managing Services

### View Status

```bash
# User:
systemctl --user status opsechat-app
systemctl --user status opsechat-tor

# System:
sudo systemctl status opsechat-app
```

### Stop Services

```bash
# User:
systemctl --user stop opsechat-app

# System:
sudo systemctl stop opsechat-app
```

### Restart Services

```bash
# User:
systemctl --user restart opsechat-app

# System:
sudo systemctl restart opsechat-app
```

### View Logs

```bash
# User (follow mode):
journalctl --user -u opsechat-app -f

# System:
sudo journalctl -u opsechat-app -f

# All related services:
journalctl --user -u opsechat-app -u opsechat-tor
```

## Troubleshooting

### Container Won't Start

1. Check if image exists:
   ```bash
   podman images localhost/opsechat
   ```

2. Verify network and volume exist:
   ```bash
   podman network ls
   podman volume ls
   ```

3. Check service logs:
   ```bash
   journalctl --user -u opsechat-app -n 50
   ```

### Tor Connection Failed

1. Verify Tor container is healthy:
   ```bash
   podman inspect opsechat-tor --format='{{.State.Health.Status}}'
   ```

2. Check Tor logs:
   ```bash
   journalctl --user -u opsechat-tor -n 50
   ```

3. Verify torrc path is correct in the quadlet file

### Cannot Access Onion Address

1. Ensure you're using Tor Browser
2. Wait 1-2 minutes for hidden service creation
3. Check logs for the full .onion URL

## Development Mode

For local development with direct Flask access (bypasses Tor):

1. Edit `opsechat-app.container`:
   ```ini
   # Uncomment this line:
   PublishPort=5000:5000
   ```

2. Reload and restart:
   ```bash
   systemctl --user daemon-reload
   systemctl --user restart opsechat-app
   ```

3. Access at `http://localhost:5000/{path}`

⚠️ **Security Warning**: Never enable port exposure in production as it bypasses Tor anonymity.

## Clean Up

Remove all opsechat containers, networks, and volumes:

```bash
# Stop services
systemctl --user stop opsechat-app opsechat-tor

# Remove quadlet files
rm ~/.config/containers/systemd/opsechat*.container
rm ~/.config/containers/systemd/opsechat*.network
rm ~/.config/containers/systemd/tor-data.volume

# Reload systemd
systemctl --user daemon-reload

# Remove resources
podman network rm opsechat-network
podman volume rm tor-data
podman rmi localhost/opsechat:latest
```

## Comparison: Quadlets vs Docker Compose

| Feature | Docker Compose | Quadlets |
|---------|---------------|----------|
| Daemon | Requires Docker daemon | Daemonless (Podman) |
| Rootless | Limited | Full support |
| Systemd | Separate management | Native integration |
| Auto-start | Needs configuration | Built-in |
| Logging | Docker logs | journalctl |
| Dependencies | compose depends_on | systemd Requires/After |
| Health checks | compose healthcheck | systemd HealthCmd |

Both deployment methods are supported - choose based on your infrastructure.

## See Also

- [DOCKER.md](DOCKER.md) - Docker/Podman Compose deployment
- [README.md](README.md) - General documentation
- [Podman Quadlet Documentation](https://docs.podman.io/en/latest/markdown/podman-quadlet.1.html)
