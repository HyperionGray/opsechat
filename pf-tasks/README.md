# PF Tasks for Opsechat

This directory contains PF (Platform Framework) tasks for building, deploying, testing, and managing the opsechat application. These tasks are compatible with the pf-web-poly-compile-helper-runner patterns.

## Available Tasks

### build.py
Builds the opsechat container image using podman or docker.

```bash
python pf-tasks/build.py
```

**Features:**
- Auto-detects podman or docker
- Builds with tag `localhost/opsechat:latest`
- Validates build success
- Shows image information after build

### deploy.py
Deploys opsechat using systemd quadlets or docker-compose.

```bash
# Auto-detect deployment method
python pf-tasks/deploy.py

# Force quadlet deployment
python pf-tasks/deploy.py --method quadlet

# Force compose deployment
python pf-tasks/deploy.py --method compose

# Use specific compose tool
python pf-tasks/deploy.py --method compose --compose-tool podman-compose
```

**Features:**
- Auto-detects available deployment methods
- Supports systemd quadlets for native systemd integration
- Supports docker-compose and podman-compose
- Installs quadlet files to appropriate systemd directories
- Enables and starts services automatically
- Sets up cleanup timers

### test.py
Tests the deployed opsechat application.

```bash
# Run all tests
python pf-tasks/test.py

# Test only containers
python pf-tasks/test.py --method container

# Test only systemd services
python pf-tasks/test.py --method systemd

# Skip end-to-end tests
python pf-tasks/test.py --skip-e2e
```

**Features:**
- Tests container health and status
- Tests systemd service status
- Tests Tor connectivity and hidden service creation
- Tests Python module imports
- Runs Playwright end-to-end tests (if available)
- Comprehensive test reporting

### clean.py
Cleans up opsechat deployment and resources.

```bash
# Clean everything
python pf-tasks/clean.py

# Clean only systemd services
python pf-tasks/clean.py --method systemd

# Clean only compose deployment
python pf-tasks/clean.py --method compose

# Also remove container images
python pf-tasks/clean.py --images

# Force removal of images
python pf-tasks/clean.py --images --force

# Clean build artifacts
python pf-tasks/clean.py --artifacts
```

**Features:**
- Stops and removes systemd services
- Removes quadlet files
- Stops and removes containers
- Removes networks and volumes
- Optionally removes container images
- Cleans build artifacts and cache

## Usage Patterns

### Complete Deployment Workflow

```bash
# 1. Build the application
python pf-tasks/build.py

# 2. Deploy using preferred method
python pf-tasks/deploy.py

# 3. Test the deployment
python pf-tasks/test.py

# 4. View the onion address
systemctl --user status opsechat-app.service
# or
docker-compose logs opsechat
```

### Development Workflow

```bash
# Build and test locally
python pf-tasks/build.py
python pf-tasks/deploy.py --method compose
python pf-tasks/test.py --method container

# Make changes, rebuild, and redeploy
python pf-tasks/clean.py --method compose
python pf-tasks/build.py
python pf-tasks/deploy.py --method compose
```

### Production Deployment

```bash
# Use systemd quadlets for production
python pf-tasks/build.py
python pf-tasks/deploy.py --method quadlet
python pf-tasks/test.py

# Services will auto-start on boot
systemctl --user enable opsechat-tor.service
systemctl --user enable opsechat-app.service
```

### Cleanup and Maintenance

```bash
# Regular cleanup (keeps images)
python pf-tasks/clean.py --method all

# Complete cleanup (removes everything)
python pf-tasks/clean.py --images --artifacts

# Clean only build artifacts
python pf-tasks/clean.py --artifacts
```

## Integration with Existing Scripts

The PF tasks are designed to work alongside existing scripts:

- `compose-up.sh` / `compose-down.sh` - Still work for compose deployments
- `verify-setup.sh` - Can be used alongside `test.py`
- Existing Docker and Podman workflows remain unchanged

## Systemd Quadlet Integration

When using `--method quadlet`, the deploy task:

1. Copies quadlet files to `~/.config/containers/systemd/` or `/etc/containers/systemd/`
2. Copies `torrc` to `~/opsechat/torrc`
3. Reloads systemd daemon
4. Enables and starts services in correct order
5. Sets up cleanup timer for maintenance

## Requirements

- Python 3.6+
- podman or docker
- systemd (for quadlet deployment)
- podman-compose or docker-compose (for compose deployment)

## Error Handling

All tasks include comprehensive error handling:
- Commands are logged before execution
- Exit codes are checked and reported
- Stderr output is captured and displayed
- Tasks exit with appropriate status codes for CI/CD integration

## Compatibility

These tasks follow pf-web-poly-compile-helper-runner patterns:
- Consistent command-line interface
- Proper exit codes for automation
- Comprehensive logging and status reporting
- Modular design for easy extension
- Support for multiple deployment methods