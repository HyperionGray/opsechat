# opsechat Installation Guide

This guide provides detailed instructions for installing opsechat on a clean Linux system.

## Table of Contents

- [Quick Start](#quick-start)
- [System Requirements](#system-requirements)
- [Automated Installation](#automated-installation)
- [Manual Installation](#manual-installation)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## Quick Start

For most users, the automated installer is the fastest way to get started:

```bash
curl -sSL https://raw.githubusercontent.com/HyperionGray/opsechat/master/install.sh | bash
```

Or download the repository first:

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
./install.sh
```

## System Requirements

### Operating System

opsechat supports the following Linux distributions:
- Ubuntu 18.04 LTS or later
- Debian 10 or later
- RHEL/CentOS 7 or later
- Fedora 30 or later
- Arch Linux (current)

### Hardware

- Minimal: 512 MB RAM, 1 GB disk space
- Recommended: 1 GB RAM, 2 GB disk space

### Software Dependencies

The installer will automatically install:
- Python 3.8 or later
- pip (Python package manager)
- Python venv module
- Tor (The Onion Router)
- Git (if not already installed)

### Network Requirements

- Internet connection for downloading packages
- Tor network access (typically works in most environments)

## Automated Installation

The automated installer (`install.sh`) performs a complete installation on a clean system.

### What the Installer Does

1. **Detects your operating system** and package manager
2. **Checks for sudo access** (required for system package installation)
3. **Updates package lists** to ensure latest versions
4. **Installs Git** if not already present
5. **Installs Python 3.8+** with pip and venv
6. **Installs Tor** from your distribution's repository
7. **Configures Tor** with ControlPort enabled for opsechat
8. **Clones or updates** the opsechat repository to `~/opsechat`
9. **Creates a Python virtual environment** in `~/opsechat/venv`
10. **Installs Python dependencies** (Flask, stem, requests)
11. **Creates a launcher script** for easy startup
12. **Verifies the installation** to ensure all components are working

### Running the Installer

#### Option 1: Direct Download and Run

```bash
curl -sSL https://raw.githubusercontent.com/HyperionGray/opsechat/master/install.sh | bash
```

This downloads and runs the installer in one command. Review the script first if you're concerned about security.

#### Option 2: Clone and Run

```bash
# Clone the repository
git clone https://github.com/HyperionGray/opsechat.git

# Navigate to the directory
cd opsechat

# Make the installer executable (if needed)
chmod +x install.sh

# Run the installer
./install.sh
```

### Installation Options

The installer is interactive and will:
- Ask for confirmation before recreating existing installations
- Request sudo password for system package installation
- Provide colored output showing progress and status

### Post-Installation

After successful installation:

1. **Start opsechat:**
   ```bash
   cd ~/opsechat
   ./start-opsechat.sh
   ```

2. **Or start manually:**
   ```bash
   cd ~/opsechat
   source venv/bin/activate
   python runserver.py
   ```

3. **Share the .onion URL** printed by the server with your chat participants

4. **Press Ctrl+C** to stop the server when done

## Manual Installation

If you prefer to install manually or need more control over the process:

### Step 1: Install System Dependencies

#### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv tor git
```

#### RHEL/CentOS

```bash
# Enable EPEL repository (for Tor)
sudo yum install -y epel-release

# Install packages
sudo yum install -y python3 python3-pip tor git
```

#### Fedora

```bash
sudo dnf install -y python3 python3-pip tor git
```

#### Arch Linux

```bash
sudo pacman -Sy python python-pip tor git
```

### Step 2: Configure Tor

Create or edit `/etc/tor/torrc`:

```bash
sudo nano /etc/tor/torrc
```

Add these lines:

```
# opsechat configuration
ControlPort 9051
CookieAuthentication 0
```

Save and restart Tor:

```bash
sudo systemctl enable tor
sudo systemctl restart tor
```

Verify Tor is running:

```bash
sudo systemctl status tor
```

### Step 3: Clone Repository

```bash
cd ~
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
```

### Step 4: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 5: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 6: Run opsechat

```bash
python runserver.py
```

The server will print an `.onion` URL that you can share with chat participants.

## Troubleshooting

### Tor Not Running

**Error:** `[!] Tor proxy or Control Port are not running`

**Solution:**
```bash
# Check Tor status
sudo systemctl status tor

# Start Tor
sudo systemctl start tor

# Enable Tor to start on boot
sudo systemctl enable tor
```

### Tor Control Port Not Accessible

**Error:** Connection refused to control port

**Solution:**
```bash
# Verify ControlPort is configured
grep ControlPort /etc/tor/torrc

# If missing, add it:
echo "ControlPort 9051" | sudo tee -a /etc/tor/torrc
echo "CookieAuthentication 0" | sudo tee -a /etc/tor/torrc

# Restart Tor
sudo systemctl restart tor
```

### Python Version Too Old

**Error:** Python 3.8 or later required

**Solution:**
```bash
# Ubuntu/Debian - add deadsnakes PPA for newer Python
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv python3.11-dev

# Use the newer Python version
python3.11 -m venv venv
```

### Permission Denied

**Error:** Permission denied during installation

**Solution:**
- Run installer as regular user (not root)
- Ensure you have sudo access: `sudo -v`
- Check file permissions: `ls -la install.sh`

### Port 5000 Already in Use

**Error:** Address already in use on port 5000

**Solution:**
```bash
# Find what's using the port
sudo lsof -i :5000

# Kill the process or use a different port
# Set FLASK_RUN_PORT environment variable
export FLASK_RUN_PORT=5001
python runserver.py
```

### Virtual Environment Activation Issues

**Error:** Cannot activate virtual environment

**Solution:**
```bash
# Recreate the virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Git Not Installed

**Error:** git: command not found

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install git

# RHEL/CentOS/Fedora
sudo dnf install git

# Arch
sudo pacman -S git
```

## Uninstallation

To remove opsechat from your system:

```bash
cd ~/opsechat
./uninstall.sh
```

The uninstaller will:
- Stop any running opsechat processes
- Remove the installation directory (`~/opsechat`)
- Optionally remove Tor configuration changes
- Preserve system packages (Python, Tor, Git)

To completely remove system packages as well:

```bash
# Ubuntu/Debian
sudo apt-get remove tor python3

# RHEL/CentOS/Fedora
sudo dnf remove tor python3

# Arch
sudo pacman -R tor python
```

## Security Considerations

### Tor Configuration

The installer configures Tor with `CookieAuthentication 0` for simplicity. This allows any local process to control Tor.

For increased security, you can:
1. Use password authentication
2. Restrict control port access to specific users
3. Use Unix socket instead of TCP port

See [SECURITY.md](SECURITY.md) for more details.

### Running as Root

**Do not run opsechat as root.** The installer will warn you if you attempt this. Always run as a regular user.

### Firewall Configuration

opsechat uses:
- Port 5000 (local Flask server - not exposed)
- Port 9051 (Tor control port - local only)
- Tor network (outbound connections)

No inbound ports need to be opened on your firewall. All connections are through Tor's hidden service.

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review [SECURITY.md](SECURITY.md) for security guidance
3. Check [README.md](README.md) for usage instructions
4. Open an issue on GitHub: https://github.com/HyperionGray/opsechat/issues

## Additional Resources

- [README.md](README.md) - General usage and features
- [SECURITY.md](SECURITY.md) - Security best practices
- [PGP_USAGE.md](PGP_USAGE.md) - PGP encryption guide
- [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md) - Email system documentation
- [TESTING.md](TESTING.md) - Running tests
