Platform
========

To be a opsechat server host requires a Linux machine (any Linux should do), if this gets more popular we will create one for Windows.

To be a opsechat client requires a Tor Browser on any OS.


Install
=======

## Option 1: Systemd Quadlets (Recommended for Production)

For production deployment with native systemd integration:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
$ ./quadlet-setup.sh
```

This provides the best integration with systemd, automatic startup, and native service management.

## Option 2: Docker/Podman Compose (Recommended for Development)

For the easiest setup with full isolation, use containers:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
$ ./compose-up.sh
```

That's it! The script will handle everything. See [DOCKER.md](DOCKER.md) for full documentation.

## Option 3: PF Tasks (Advanced Users)

For advanced deployment automation using PF tasks:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
$ python pf-tasks/build.py
$ python pf-tasks/deploy.py
$ python pf-tasks/test.py
```

See [pf-tasks/README.md](pf-tasks/README.md) for complete PF tasks documentation.

## Option 4: Native Installation

### Quick Install (Recommended)

For a clean box installation that automatically installs all dependencies:

**Option 1: Download and run (recommended)**
```bash
# Clone the repository first
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat

# Review the script if desired
less install.sh

# Run the installer
./install.sh
```

**Option 2: Direct download and run**
```bash
# Download and run in one step (use with caution)
curl -sSL https://raw.githubusercontent.com/HyperionGray/opsechat/master/install.sh | bash
```

The installer will:
- Detect your Linux distribution (Ubuntu/Debian, RHEL/CentOS/Fedora, Arch)
- Install system dependencies (Python 3.8+, Tor, Git)
- Configure Tor with control port enabled
- Create a Python virtual environment
- Install all Python dependencies
- Create a launcher script for easy startup

**Supported Operating Systems:**
- Ubuntu/Debian (using apt)
- RHEL/CentOS/Fedora (using yum/dnf)
- Arch Linux (using pacman)

**Requirements:**
- Root/sudo access for system package installation
- Internet connection

After installation, start opsechat with:
```bash
cd ~/opsechat
./start-opsechat.sh
```

## Manual Install

If you prefer to install manually or need more control:

1. Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv tor git

# RHEL/CentOS/Fedora
sudo dnf install -y python3 python3-pip tor git

# Arch
sudo pacman -S python python-pip tor git
```

2. Configure Tor:
```bash
sudo bash -c 'echo "ControlPort 9051" >> /etc/tor/torrc'
sudo bash -c 'echo "CookieAuthentication 0" >> /etc/tor/torrc'
sudo systemctl restart tor
```

3. Clone and setup opsechat:
```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. Run the server:
```bash
python runserver.py
```

## Uninstall

To remove opsechat:
```bash
cd ~/opsechat
./uninstall.sh
```

This will remove the installation directory and optionally clean up Tor configuration, while preserving system packages.

Testing
=======

The project includes comprehensive automated tests using Playwright. See [TESTING.md](TESTING.md) for detailed instructions.

Quick start:

```bash
# Install test dependencies
npm install
npx playwright install

# Run headless tests (no browser window)
npm run test:headless

# Run tests with visible browser (for debugging)
npm run test:headed

# Run all tests
npm test
```

Tests cover:
- Project structure and dependencies
- Python module imports
- Flask routes and session handling
- UI functionality (script and noscript modes)
- Security headers validation
- Responsive design

For full testing documentation, see [TESTING.md](TESTING.md).


How it works
============

You'll see this when it first loads up:

```
(venv) alejandrocaceres@Alejandros-MacBook-Pro ~/o/d/dropchat (master) [1]> python runserver.py
[*] Connecting to tor
[*] Creating ephemeral hidden service, this may take a minute or two
[*] Started a new hidden service with the address of l7k4f6ie2nr6nnfscxxh4e4wref5dgaelunx5mjctt66mhfyky4rv6id.onion
[*] Your service is available at: l7k4f6ie2nr6nnfscxxh4e4wref5dgaelunx5mjctt66mhfyky4rv6id.onion/wdLEcxKPd6ARir3m2t2bFlJfX0q5q6jP , press ctrl+c to quit
 * Serving Flask app 'runserver' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 ```

Dropchat is a disposable mini-chat server that can be used to chat safely and anonymously through Tor. One
person is the host of the chat server (don't worry being a host only requires one command - no messing with
complex config files) and the others are the clients using only a Tor Browser. The host starts the server 
and shares a URL with the clients. They can then chat with each other safely and anonymously. Once you're 
done sharing the info you want, simply kill the server. No information is stored on disk.

Usage
=====

Share the drop URL with your friends to open in Tor Browser. Chat with them safely and securely! Chatting looks like this:

<img width="1194" alt="dropchat" src="https://user-images.githubusercontent.com/3106718/144932238-5363d4eb-40f8-451f-80f3-3bc8259c0475.png">


Javascript
==========

You have the option of using Javascript or not. In order to use it go to noscript -> options -> add the hostname
to the whitelist (not the url). Then click on the link at the top of the page to go to the script-allowed version
of dropchat if you are not redirected. This is for when you trust the people you are chatting with somewhat, the 
user experience is significantly improved with Javascript.

To not use javascript simply leave noscript on (or the "safest" setting in TBB).

Features
========

### Chat System
- As chat happens inside the Tor network via ephemeral hidden services, everything is encrypted and attribution of chatters is virtually impossible
- *Nothing* touches disk except the app, everything happens in-memory, no chat, image, video, or ANYTHING caching to storage.
- This chat is meant to help you with opsec, disappearing messages, randomized usernames, encrypted comms are the default (much more to come)
- **PGP encryption support** - Optional end-to-end encryption using PGP keys (see [PGP_USAGE.md](PGP_USAGE.md))
- No configuration required
- Low barrier to entry, few dependencies
- No need for a client
- Chats are deleted every 3 minutes
- Randomized usernames - this is for your own safety, so as to decrease chances of username reuse
- New chat service created every time the server is started
- No frills, no fancy CSS, code is easy to follow and review to ensure your safety

### Email System (NEW - REAL EMAIL SUPPORT!)
- **Real SMTP/IMAP Integration** - Send and receive actual emails via configured email servers (see [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md))
- **Encrypted Email Inbox** - In-memory email storage with PGP support
- **Raw Mode Editing** - Full control over email headers for security testing
- **Modern Burner Email System** - Guerrillamail-style rotating anonymous email addresses with:
  - **Multi-Burner Management** - Keep multiple active burner emails simultaneously
  - **Live Countdown Timers** - Real-time expiry tracking with JavaScript
  - **Quick Rotation** - One-click generation and rotation to new addresses
  - **Instant Copy** - Copy burner emails to clipboard with one click
  - **Smart Stats Dashboard** - Track active burners and total time remaining
- **Automated Domain Purchasing** - Porkbun API integration for cheap domain rotation (.xyz, .club, etc.)
- **Budget Management** - Configurable monthly spending limits for domain purchases
- **Spoofing Detection** - Test emails for spoofing attempts (unicode lookalikes, typosquatting, homographs)
- **Phishing Simulation** - Gamified training with scoring and achievements
- **Security Research Tools** - For authorized penetration testing and awareness training
- **Plain Text Only** - HTML and images are shown as text for security analysis
- JavaScript optional throughout

#### Getting Started with Email
1. Start the server: `python runserver.py` or use deployment method above
2. Access email configuration: `http://yourservice.onion/{path}/email/config`
3. Configure SMTP for sending (optional): Add your email server settings
4. Configure IMAP for receiving (optional): Add your IMAP server settings
5. Configure Porkbun API for domain rotation (optional): Add API credentials and budget (see [DOMAIN_API_SETUP.md](DOMAIN_API_SETUP.md))
6. Compose and send emails: `http://yourservice.onion/{path}/email/compose`
7. View your inbox: `http://yourservice.onion/{path}/email`

For full documentation, see [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md).

Security
========

For security best practices and recommendations, please see [SECURITY.md](SECURITY.md).

**Note on jQuery**: The bundled jQuery (v3.3.1) should be updated to v3.7.1 or later to patch known XSS vulnerabilities. Download the latest version from https://code.jquery.com/jquery-3.7.1.min.js and replace `static/jquery.js`.

---

[![define hyperion gray](https://hyperiongray.s3.amazonaws.com/define-hg.svg)](https://www.hyperiongray.com/?pk_campaign=github&pk_kwd=dropchat "Hyperion Gray")
