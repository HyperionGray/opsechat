# Container Deployment Testing Guide

## Overview

This document describes how to test the containerized deployment of OpSecChat using Docker or Podman.

## Prerequisites

- Docker or Podman installed
- docker-compose or podman-compose installed
- At least 2GB of free disk space
- Port 5000 available (for testing with exposed ports)

## Container Build Test

### Test 1: Build the Container Image

```bash
# Using Podman (recommended)
podman build -t localhost/opsechat:latest .

# Using Docker
docker build -t opsechat:latest .
```

**Expected Result:**
- Build completes successfully
- No errors during Python dependency installation
- Image is created with all necessary files

**Validation:**
```bash
# Check image exists
podman images | grep opsechat
# or
docker images | grep opsechat
```

### Test 2: Inspect Container Structure

```bash
# Using Podman
podman run --rm opsechat:latest ls -la /app

# Using Docker
docker run --rm opsechat:latest ls -la /app
```

**Expected Files:**
- `runserver.py`
- `email_system.py`
- `email_security_tools.py`
- `email_transport.py`
- `domain_manager.py`
- `static/` directory
- `templates/` directory

## Container Startup Test

### Test 3: Start with Docker Compose

```bash
# Start all services
./compose-up.sh

# Check status
docker-compose ps
# or
podman-compose ps
```

**Expected Result:**
- Two containers running:
  - `opsechat-tor` (Tor daemon)
  - `opsechat-app` (OpSecChat application)
- Both containers show "healthy" or "running" status

### Test 4: Verify Tor Service

```bash
# Check Tor is accessible
docker-compose exec tor nc -z localhost 9051
# or
podman-compose exec tor nc -z localhost 9051
```

**Expected Result:**
- Connection succeeds (exit code 0)
- Tor control port is accessible

### Test 5: View Application Logs

```bash
# View OpSecChat logs
docker-compose logs opsechat
# or
podman-compose logs opsechat
```

**Expected Output:**
- Flask server starting message
- Tor connection messages
- Hidden service .onion address displayed

## Functionality Tests

### Test 6: Access Health and Readiness Endpoints

If you've exposed port 5000 for testing:

```bash
# In docker-compose.yml, uncomment:
# ports:
#   - "5000:5000"

# Then restart
./compose-down.sh
./compose-up.sh

# Test health and readiness endpoints
curl http://localhost:5000/health
curl http://localhost:5000/ready
```

**Expected Result:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-02T..."
}
```

Readiness should also return HTTP 200 with a payload that includes `"ready": true`.

### Test 7: Verify Chat Functionality

With ports exposed:

```bash
# Create a test room
curl -X POST http://localhost:5000/chat/create
```

**Expected Result:**
```json
{
  "success": true,
  "room_id": "...",
  "room_url": "/chat/room/..."
}
```

### Test 8: Verify Email Routes

```bash
# Access email configuration page
curl http://localhost:5000/<secret-path>/email/config
```

**Expected Result:**
- HTTP 200 OK
- HTML content with email configuration form

## Network Isolation Tests

### Test 9: Verify Internal Network

```bash
# Check containers are on same network
docker network inspect opsechat_opsechat-network
# or
podman network inspect opsechat_opsechat-network
```

**Expected Result:**
- Both containers listed in network
- Containers can communicate with each other

### Test 10: Verify Tor Connectivity from App

```bash
# Enter app container
docker-compose exec opsechat bash
# Inside container:
nc -z tor 9051
```

**Expected Result:**
- Connection succeeds
- App can reach Tor daemon

## Resource Usage Tests

### Test 11: Monitor Container Resources

```bash
# Check resource usage
docker stats
# or
podman stats
```

**Expected Result:**
- Memory usage < 500MB per container
- CPU usage reasonable (<50% under light load)

### Test 12: Check Disk Usage

```bash
# Check image sizes
docker images | grep opsechat
# or
podman images | grep opsechat
```

**Expected Result:**
- opsechat image < 500MB
- tor image < 100MB

## Persistence Tests

### Test 13: Data Persistence Across Restarts

```bash
# Stop services
./compose-down.sh

# Start again
./compose-up.sh

# Check if Tor data volume persists
docker volume ls | grep tor-data
# or
podman volume ls | grep tor-data
```

**Expected Result:**
- `tor-data` volume exists
- Volume retained between restarts

### Test 14: Clean Restart

```bash
# Stop and remove all containers and volumes
./compose-down.sh -v

# Start fresh
./compose-up.sh
```

**Expected Result:**
- New containers created
- New hidden service address generated
- All data cleared

## Security Tests

### Test 15: Verify No Port Exposure (Production Mode)

Ensure ports are commented out in `docker-compose.yml`:

```bash
# Check no ports exposed to host
docker-compose ps
# or
podman-compose ps
```

**Expected Result:**
- No ports listed in PORTS column
- Access only via Tor

### Test 16: Verify Tor Hidden Service

```bash
# Get hidden service address
docker-compose logs opsechat | grep ".onion"
# or
podman-compose logs opsechat | grep ".onion"
```

**Expected Result:**
- Hidden service address displayed
- Format: `[random].onion/[random-path]`

## Cleanup

### Stop All Services

```bash
./compose-down.sh
```

### Remove All Data

```bash
./compose-down.sh -v
```

### Remove Images

```bash
# Podman
podman rmi localhost/opsechat:latest

# Docker
docker rmi opsechat:latest
```

## Troubleshooting

### Container Won't Start

**Problem:** Container exits immediately

**Solution:**
```bash
# Check logs
docker-compose logs opsechat

# Common issues:
# 1. Port 5000 already in use
# 2. Tor not accessible
# 3. Missing dependencies
```

### Tor Connection Failed

**Problem:** App can't connect to Tor

**Solution:**
```bash
# Check Tor is running
docker-compose ps tor

# Check Tor health
docker-compose logs tor

# Restart Tor
docker-compose restart tor
```

### Permission Errors

**Problem:** Permission denied errors in container

**Solution:**
```bash
# Check file permissions
ls -la .

# If using Podman, may need to add :Z to volume mounts
# In docker-compose.yml:
# volumes:
#   - ./torrc:/etc/tor/torrc:ro,Z
```

## Automated Test Script

Create a script `test-container.sh`:

```bash
#!/bin/bash
set -e

echo "=== OpSecChat Container Tests ==="

echo "1. Building container..."
podman build -t localhost/opsechat:latest .

echo "2. Starting services..."
./compose-up.sh

echo "3. Waiting for services to be ready..."
sleep 10

echo "4. Checking Tor health..."
podman-compose exec -T tor nc -z localhost 9051

echo "5. Checking OpSecChat logs..."
podman-compose logs opsechat | grep -q "Running on"

echo "6. Stopping services..."
./compose-down.sh

echo "=== All tests passed! ==="
```

Make it executable:
```bash
chmod +x test-container.sh
./test-container.sh
```

## Summary

This test guide covers:
- ✅ Container build process
- ✅ Service startup and health checks
- ✅ Network connectivity
- ✅ Functionality verification
- ✅ Resource usage monitoring
- ✅ Data persistence
- ✅ Security validation
- ✅ Cleanup procedures

All paths have been tested to ensure smooth deployment and operation.
