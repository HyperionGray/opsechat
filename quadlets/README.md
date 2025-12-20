# Systemd Quadlets for Opsechat

This directory contains systemd quadlet files for deploying opsechat using native systemd container management. Quadlets provide a systemd-native way to manage containers without requiring docker-compose or podman-compose.

## Files

### Container Definitions

- **opsechat-tor.container** - Tor daemon container
- **opsechat-app.container** - Main opsechat application container
- **opsechat.network** - Container network definition

### Service Definitions

- **opsechat-cleanup.service** - Cleanup service for maintenance tasks
- **opsechat-cleanup.timer** - Timer to run cleanup service daily

## Installation

### Automatic Installation (Recommended)

Use the PF deploy task:

```bash
python pf-tasks/deploy.py --method quadlet
```

### Manual Installation

1. **Copy quadlet files to systemd directory:**

   For user services (recommended):
   ```bash
   mkdir -p ~/.config/containers/systemd
   cp quadlets/*.container ~/.config/containers/systemd/
   cp quadlets/*.network ~/.config/containers/systemd/
   cp quadlets/*.service ~/.config/containers/systemd/
   cp quadlets/*.timer ~/.config/containers/systemd/
   ```

   For system services (requires root):
   ```bash
   sudo mkdir -p /etc/containers/systemd
   sudo cp quadlets/*.container /etc/containers/systemd/
   sudo cp quadlets/*.network /etc/containers/systemd/
   sudo cp quadlets/*.service /etc/containers/systemd/
   sudo cp quadlets/*.timer /etc/containers/systemd/
   ```

2. **Copy torrc configuration:**
   ```bash
   mkdir -p ~/opsechat
   cp torrc ~/opsechat/torrc
   ```

3. **Reload systemd and start services:**
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable opsechat.network
   systemctl --user enable opsechat-tor.service
   systemctl --user enable opsechat-app.service
   systemctl --user start opsechat.network
   systemctl --user start opsechat-tor.service
   systemctl --user start opsechat-app.service
   ```

4. **Enable cleanup timer:**
   ```bash
   systemctl --user enable opsechat-cleanup.timer
   systemctl --user start opsechat-cleanup.timer
   ```

## Usage

### Service Management

```bash
# Check service status
systemctl --user status opsechat-app.service
systemctl --user status opsechat-tor.service
systemctl --user status opsechat.network

# View logs
journalctl --user -u opsechat-app.service -f
journalctl --user -u opsechat-tor.service -f

# Restart services
systemctl --user restart opsechat-app.service

# Stop all services
systemctl --user stop opsechat-app.service
systemctl --user stop opsechat-tor.service
systemctl --user stop opsechat.network
```

### Getting the Onion Address

```bash
# View application logs to find the onion address
journalctl --user -u opsechat-app.service | grep "Your service is available at"

# Or check current status
systemctl --user status opsechat-app.service
```

### Cleanup Timer Management

```bash
# Check cleanup timer status
systemctl --user status opsechat-cleanup.timer

# View cleanup logs
journalctl --user -u opsechat-cleanup.service

# Run cleanup manually
systemctl --user start opsechat-cleanup.service
```

## Architecture

### Service Dependencies

```
opsechat.network
    ↓
opsechat-tor.service
    ↓
opsechat-app.service
```

### Container Network

All containers run on the `opsechat-network` bridge network, providing isolation while allowing inter-container communication.

### Volume Mounts

- **Tor container**: 
  - `~/opsechat/torrc` → `/etc/tor/torrc` (read-only)
  - `opsechat-tor-data` volume → `/var/lib/tor` (persistent Tor data)

- **App container**: No persistent volumes (pure in-memory operation)

## Security Features

### Network Isolation
- Containers communicate only via dedicated bridge network
- No host ports exposed (Tor-only access)
- Internal network traffic only

### Service Isolation
- Each container runs with minimal privileges
- Tor daemon isolated from application
- Health checks ensure service reliability

### Automatic Updates
- Tor container: `AutoUpdate=registry` (pulls latest Alpine)
- App container: `AutoUpdate=local` (uses locally built image)

## Troubleshooting

### Services Won't Start

1. **Check systemd status:**
   ```bash
   systemctl --user status opsechat-tor.service
   systemctl --user status opsechat-app.service
   ```

2. **Check logs:**
   ```bash
   journalctl --user -u opsechat-tor.service
   journalctl --user -u opsechat-app.service
   ```

3. **Verify quadlet files:**
   ```bash
   ls ~/.config/containers/systemd/
   systemctl --user daemon-reload
   ```

### Container Issues

1. **Check if containers exist:**
   ```bash
   podman ps -a
   ```

2. **Check container logs directly:**
   ```bash
   podman logs opsechat-tor
   podman logs opsechat-app
   ```

3. **Rebuild image if needed:**
   ```bash
   python pf-tasks/build.py
   systemctl --user restart opsechat-app.service
   ```

### Network Issues

1. **Check network exists:**
   ```bash
   podman network ls
   ```

2. **Recreate network:**
   ```bash
   systemctl --user restart opsechat.network
   ```

### Permission Issues

1. **For user services:**
   ```bash
   # Enable lingering to allow user services to start at boot
   sudo loginctl enable-linger $USER
   ```

2. **For system services:**
   ```bash
   # Use system-wide quadlet directory
   sudo cp quadlets/* /etc/containers/systemd/
   sudo systemctl daemon-reload
   ```

## Advantages of Quadlets

### Over Docker Compose
- Native systemd integration
- Better service dependency management
- Automatic startup on boot (with lingering)
- Standard systemd logging and monitoring
- No additional compose tools required

### Over Manual Container Management
- Declarative configuration
- Automatic dependency handling
- Health checks and restart policies
- Timer-based maintenance tasks
- Standard systemd service management

## Requirements

- systemd 247+ (for quadlet support)
- podman 4.0+ (recommended) or docker with systemd integration
- User lingering enabled for boot startup (optional)

## Migration from Docker Compose

To migrate from docker-compose to quadlets:

1. **Stop compose deployment:**
   ```bash
   ./compose-down.sh
   ```

2. **Deploy with quadlets:**
   ```bash
   python pf-tasks/deploy.py --method quadlet
   ```

3. **Verify functionality:**
   ```bash
   python pf-tasks/test.py --method systemd
   ```

The quadlet deployment provides identical functionality to the compose deployment while offering better systemd integration.
