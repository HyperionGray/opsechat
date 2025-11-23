# Docker/Podman Containerization

This document describes how to run opsechat using containers with either Docker or Podman.

## Overview

The containerized setup includes:
- **Tor daemon container**: Runs the Tor service with control port enabled
- **Opsechat application container**: Runs the Flask application with chat, email, and burner email features

## Prerequisites

You need either:
- **Podman** and **podman-compose** (recommended for rootless operation)
  - Install: https://podman.io/getting-started/installation
  - Podman-compose: `pip install podman-compose`

OR

- **Docker** and **docker-compose**
  - Install: https://docs.docker.com/get-docker/

## Quick Start

### Starting Services

Simply run:

```bash
./compose-up.sh
```

This script will:
1. Detect whether you have podman-compose or docker-compose
2. Build the opsechat container image
3. Start the Tor daemon
4. Start the opsechat application
5. Display status and instructions

### Viewing the Onion Address

After services start, view the logs to get your onion service URL:

```bash
# For podman-compose
podman-compose logs opsechat

# For docker-compose
docker-compose logs opsechat
```

Look for a line like:
```
[*] Your service is available at: abc123...xyz.onion/randompath
```

### Viewing Logs

Watch logs in real-time:

```bash
# For podman-compose
podman-compose logs -f

# For docker-compose  
docker-compose logs -f
```

### Stopping Services

Run:

```bash
./compose-down.sh
```

To also remove persistent data (Tor keys):

```bash
# For podman-compose
podman-compose down -v

# For docker-compose
docker-compose down -v
```

## Manual Usage

If you prefer to run compose commands directly:

```bash
# Start services
podman-compose up -d
# or
docker-compose up -d

# View logs
podman-compose logs -f
# or
docker-compose logs -f

# Stop services
podman-compose down
# or
docker-compose down
```

## Architecture

### Network Configuration

- Both containers run in an isolated `opsechat-network` bridge network
- The opsechat app connects to the Tor daemon via the control port (9051)
- **No ports are exposed to the host by default for security**
- Access is **only through the Tor hidden service** (.onion address)
- For debugging/development, you can uncomment the port mapping in docker-compose.yml

### Security Considerations

1. **No Host Port Exposure**: By default, no ports are exposed to the host. The application is only accessible via the Tor hidden service, maintaining anonymity.
2. **Cookie Authentication**: Tor uses cookie authentication instead of password authentication for better security.
3. **Isolated Network**: Containers communicate via a dedicated bridge network, isolated from the host.
4. **Internal-Only Ports**: Tor control port and SOCKS proxy are only accessible within the container network.
5. **No Disk Storage**: The opsechat app stores nothing on disk (in-memory only).
6. **Ephemeral Hidden Services**: Services are created dynamically and destroyed on shutdown.

## Configuration

### Environment Variables

You can customize the setup by setting environment variables in `docker-compose.yml`:

- `TOR_CONTROL_HOST`: Hostname of Tor daemon (default: `tor`)
- `TOR_CONTROL_PORT`: Control port (default: `9051`)
- `FLASK_DEBUG`: Enable Flask debug mode (default: `0`)

### Custom Tor Configuration

Edit `torrc` to customize Tor settings. After changes, rebuild:

```bash
podman-compose up -d --build
# or
docker-compose up -d --build
```

### Development/Debugging Mode

For local development and debugging, you may want to expose Flask directly:

1. Edit `docker-compose.yml` and uncomment the ports section under `opsechat`:
   ```yaml
   ports:
     - "5000:5000"
   ```

2. Restart services:
   ```bash
   ./compose-down.sh
   ./compose-up.sh
   ```

3. Access directly at `http://localhost:5000/{path}`

**⚠️ WARNING**: Only use this for development. Never expose Flask directly in production as it bypasses Tor anonymity.

## Troubleshooting

### Services won't start

Check logs for errors:
```bash
podman-compose logs
```

### Can't connect to Tor

Verify Tor is running:
```bash
podman-compose ps
```

Check Tor logs:
```bash
podman-compose logs tor
```

### Opsechat can't create hidden service

This usually means:
1. Tor isn't fully started yet (wait 10-30 seconds)
2. Control port authentication failed (check torrc configuration)
3. Network connectivity issues between containers

Restart services:
```bash
./compose-down.sh
./compose-up.sh
```

### Permission denied errors (Podman only)

If running rootless Podman and getting permission errors:
```bash
podman unshare chown -R 0:0 /path/to/opsechat
```

## Development

### Rebuilding Containers

After code changes:
```bash
podman-compose up -d --build
# or
docker-compose up -d --build
```

### Running Tests

Tests should be run outside containers on the host:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/
```

### Accessing Container Shell

```bash
# Opsechat app
podman exec -it opsechat-app /bin/bash
# or
docker exec -it opsechat-app /bin/bash

# Tor daemon
podman exec -it opsechat-tor /bin/sh
# or
docker exec -it opsechat-tor /bin/sh
```

## Production Considerations

While this setup provides good isolation, for production use consider:

1. **Use a reverse proxy** (nginx, traefik) in front of Flask
2. **Use a production WSGI server** (gunicorn, uwsgi) instead of Flask's dev server
3. **Set up monitoring** and health checks
4. **Regular security updates** of container images
5. **Backup Tor keys** if you need persistent onion addresses (not recommended for this use case)
6. **Resource limits** via docker-compose constraints

## Differences from Native Setup

Containerized vs. native:
- **Isolation**: Better process isolation and resource management
- **Dependencies**: All dependencies bundled, no system conflicts
- **Portability**: Easy to deploy on any Docker/Podman host
- **Overhead**: Slight performance overhead from containerization
- **Networking**: Additional network layer between components

## Support

For issues specific to containerization, check:
1. Container logs: `podman-compose logs` or `docker-compose logs`
2. Container status: `podman-compose ps` or `docker-compose ps`
3. Network connectivity: `podman network inspect opsechat-network`

For general opsechat issues, see the main [README.md](README.md).
