**Version:** 0.8.0-alpha  
**Documentation:** [docs/README.md](docs/README.md)  
**License:** MIT

## 🆕 NEW: Enhanced Security & Production Ready

**Latest Updates (v0.8.0):**
- 🔑 **Automated Key Exchange** - No manual key sharing needed
- 💬 **Direct Messages** - Ephemeral DM feature for sharing room IDs (1-min expiry)
- 🔒 **Non-Discoverable Room IDs** - Cryptographically secure 256-bit tokens
- 🌐 **Domain Rotation CLI** - Easy burner email domain management
- 📧 **Email Rate Limiting** - 10 emails/hour to prevent abuse
- ⚠️ **Strong Security Warnings** - Clear messaging about acceptable use
- 🚀 **Production Deployment** - Robust systemd units with auto-restart

📖 **Full Details:** [New Features Guide](docs/NEW_FEATURES.md)

---

## 🆕 Simple Web-Based Chat Rooms

**Secure, ephemeral chat rooms with one command - Web or TUI.**

OpSecChat now includes both **Web-Based Chat Rooms** and **Terminal UI (TUI)** for maximum flexibility:

### Web Chat Rooms
- ✅ **Simple Room Creation** - One command to create a secure chat room
- ✅ **Automated E2E Encryption** - Automatic key exchange, no manual setup
- ✅ **Terminal-Style UI** - Clean, minimal interface with no flashy elements
- ✅ **Messages Burn** - Auto-delete after 3 minutes with memory overwriting
- ✅ **Randomized Usernames** - Color-coded for easy distinction
- ✅ **Text Only** - No images, videos, or media sharing (500 char limit)
- ✅ **In-Memory Only** - Zero disk writes
- ✅ **Tor Ready** - Works seamlessly with Tor hidden services
- ✅ **Direct Messages** - Share room IDs securely (1-minute expiry)

### Quick Start (Web Chat)

```bash
# Create a local chat room
python chat-room.py

# Create a Tor hidden service chat room
python chat-room.py --tor
```

Access the chat at `/chat` to create rooms and share with your contacts.

### Terminal UI (TUI)
- ✅ **TUI Only** - No web browser required
- ✅ **Tor Integration** - Built-in Tor hidden service support
- ✅ **Messages Burn** - Auto-delete after 3 minutes with overwriting
- ✅ **Randomized Usernames** - Server-assigned, no reuse
- ✅ **Text Only** - No images, videos, or encoded data
- ✅ **In-Memory Only** - Zero disk writes

### Quick Start (TUI)

```bash
# Terminal 1: Start server
python tui-server.py

# Terminal 2: Connect client
python tui-client.py
```

**With Tor:**
```bash
# Start Tor
tor --ControlPort 9051 --CookieAuthentication 1

# Start server with Tor hidden service
python tui-server.py --tor
```

📖 **Full TUI Guide:** [TUI_README.md](TUI_README.md) | [Quick Start](docs/TUI_QUICKSTART.md)

---

Platform
========

To be a opsechat server host requires a Linux machine (any Linux should do), if this gets more popular we will create one for Windows.

To be a opsechat client requires a Tor Browser on any OS.


Install
=======

## Option 1: AWS Cloud Deployment (Recommended for Production)

For production deployment with enterprise-grade security and scalability:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
# Configure AWS credentials in repository secrets
# Deploy infrastructure using CloudFormation
$ aws cloudformation create-stack --stack-name opsechat-infrastructure-production \
  --template-body file://aws/cloudformation/opsechat-infrastructure.yml \
  --parameters ParameterKey=Environment,ParameterValue=production
```

This provides AWS ECS Fargate deployment with Tor integration, network isolation, and comprehensive security monitoring. See [AWS Deployment Guide](docs/setup/AWS_DEPLOYMENT.md) for complete instructions.

## Option 2: Systemd Quadlets (Recommended for Local Production)

For local production deployment with native systemd integration:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
$ sudo podman build --runtime=runc --network host -t localhost/opsechat:latest .
$ ./install-quadlets.sh
$ systemctl --user start opsechat-app
```

This provides the best integration with systemd, automatic startup, and native service management.

## Option 3: Docker/Podman Compose (Recommended for Development)

For the easiest setup with full isolation, use containers:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
$ ./compose-up.sh
```

That's it! The script will handle everything. See [Docker Guide](docs/setup/DOCKER.md) for full documentation.

### Podman Quadlets (systemd integration)

For production deployments with systemd integration:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
$ podman build -t localhost/opsechat:latest .
$ ./install-quadlets.sh
$ systemctl --user start opsechat-app
```

See [Quadlets Guide](docs/setup/QUADLETS.md) for full documentation.

## Option 4: Native Installation (Deprecated)

Native installers (`install.sh`, `uninstall.sh`) are deprecated in favor of container/quadlet deployment. They now require `ALLOW_DEPRECATED_INSTALL=1` to run and are no longer maintained. Use quadlets or compose unless you have a specific legacy need.

## Uninstall

To remove opsechat:
```bash
cd ~/opsechat
./uninstall.sh
```

This will remove the installation directory and optionally clean up Tor configuration, while preserving system packages.

Testing
=======

The project includes comprehensive automated tests using Playwright. See [Testing Guide](docs/user-guide/TESTING.md) for detailed instructions.

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

For full testing documentation, see [Testing Guide](docs/user-guide/TESTING.md).


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
- **Simple Web Chat Rooms** - Create secure chat rooms with one command (`python chat-room.py`)
- **E2E Encryption** - Optional encryption using Web Crypto API (simple, reviewable JavaScript)
- **Terminal-Style UI** - Clean, minimal interface focused on security over aesthetics
- As chat happens inside the Tor network via ephemeral hidden services, everything is encrypted and attribution of chatters is virtually impossible
- *Nothing* touches disk except the app, everything happens in-memory, no chat, image, video, or ANYTHING caching to storage.
- This chat is meant to help you with opsec, disappearing messages, randomized usernames, encrypted comms are the default (much more to come)
- **PGP encryption support** - Optional end-to-end encryption using PGP keys (see [PGP Usage Guide](docs/user-guide/PGP_USAGE.md))
- No configuration required
- Low barrier to entry, few dependencies
- No need for a client (web-based or TUI available)
- Chats are deleted every 3 minutes
- Randomized usernames with color distinction - this is for your own safety, so as to decrease chances of username reuse
- New chat service created every time the server is started
- No frills, no fancy CSS, code is easy to follow and review to ensure your safety
- **Memory Overwriting** - Messages are overwritten in memory before deletion for enhanced security

### Email System (NEW - REAL EMAIL SUPPORT!)
- **Real SMTP/IMAP Integration** - Send and receive actual emails via configured email servers (see [Email System Guide](docs/user-guide/EMAIL_SYSTEM.md))
- **HTTP Mailboxes (No SMTP/IMAP)** - Ephemeral mailbox addresses with private read keys at `/{path}/mail`; supports both JSON API and form-based sending
- **Encrypted Email Inbox** - In-memory email storage with PGP support
- **Raw Mode Editing** - Full control over email headers for security testing
- **Modern Burner Email System** - Guerrillamail-style rotating anonymous email addresses with:
  - **Multi-Burner Management** - Keep multiple active burner emails simultaneously
  - **Live Countdown Timers** - Real-time expiry tracking with JavaScript
  - **Quick Rotation** - One-click generation and rotation to new addresses
  - **Instant Copy** - Copy burner emails to clipboard with one click
  - **Smart Stats Dashboard** - Track active burners and total time remaining
- **Automated Domain Purchasing** - Porkbun API integration for cheap domain rotation (.xyz, .club, etc.) - see [Domain Registrar API](docs/setup/DOMAIN_REGISTRAR_API.md)
- **Budget Management** - Configurable monthly spending limits for domain purchases
- **Spoofing Detection** - Test emails for spoofing attempts (unicode lookalikes, typosquatting, homographs)
- **Phishing Simulation** - Gamified training with scoring and achievements
- **Security Research Tools** - For authorized penetration testing and awareness training
- **Plain Text Only** - HTML and images are shown as text for security analysis
- JavaScript optional throughout

### Amazon Q Code Review Integration (NEW!)
- **Automated Code Reviews** - Amazon Q Developer integration for comprehensive code analysis
- **Security Scanning** - CodeWhisperer-powered vulnerability detection
- **Code Quality Analysis** - AI-powered maintainability and complexity assessment
- **Architecture Review** - Design pattern analysis and architectural recommendations
- **Custom Review Rules** - Configurable quality thresholds and security patterns
- **GitHub Actions Integration** - Automatic reviews on every push and PR
- **Mock Mode Fallback** - Local analysis when AWS services are unavailable
- **Comprehensive Reporting** - Detailed markdown reports with actionable recommendations

For Amazon Q setup instructions, see [Amazon Q Setup Guide](docs/setup/AMAZON_Q_SETUP_GUIDE.md).

#### Getting Started with Email
1. Start the server: `python runserver.py` or use deployment method above
2. Access email configuration: `http://yourservice.onion/{path}/email/config`
3. Configure SMTP for sending (optional): Add your email server settings
4. Configure IMAP for receiving (optional): Add your IMAP server settings
5. Configure Porkbun API for domain rotation (optional): Add API credentials and budget (see [Domain API Setup Guide](docs/setup/DOMAIN_API_SETUP.md))
6. Compose and send emails: `http://yourservice.onion/{path}/email/compose`
7. View your inbox: `http://yourservice.onion/{path}/email`
8. Optional HTTP mailbox flow (no SMTP/IMAP): create mailbox at `http://yourservice.onion/{path}/mail`

For full documentation, see [Email System Guide](docs/user-guide/EMAIL_SYSTEM.md).

Security & Code Quality
=======================

## Amazon Q Code Review Integration ✅

This project includes comprehensive Amazon Q Code Review integration with automated security scanning, performance optimization, and architecture validation.

**Latest Review Status (2026-01-06)**: ✅ **EXCELLENT** - No critical issues, approved for production use

### Automated Security Scanning
- **Continuous Monitoring**: GitHub Actions workflow runs security scans on every push and pull request
- **Multi-Tool Analysis**: Bandit, Safety, Semgrep, and CodeQL for comprehensive coverage
- **Custom Rules**: OpSecChat-specific security rules for Tor and PGP handling
- **Zero Vulnerabilities**: All critical and high-severity issues in project code have been addressed
- **Project Dependencies**: 0 vulnerabilities found (all dependencies up to date)

### AWS Integration
- **Production Deployment**: Complete AWS ECS Fargate infrastructure with CloudFormation
- **Security Hardening**: VPC isolation, Secrets Manager, and comprehensive monitoring
- **Cost Optimization**: Right-sized resources with estimated $65-90/month operational cost
- **Enterprise Ready**: Follows AWS Well-Architected Framework principles

### Performance Optimization
- **Memory Management**: Automatic cleanup with bounded storage (3-minute chat expiry)
- **Algorithm Efficiency**: Critical bug fixes applied for index deletion operations
- **Resource Optimization**: Container limits and health checks for reliability
- **Monitoring**: CloudWatch integration with appropriate retention policies

For detailed information, see:
- [Latest Amazon Q Code Review (2026-01-06)](docs/assessment/AMAZON_Q_CODE_REVIEW_2026-01-06.md) - ✅ **EXCELLENT** rating
- [Amazon Q Implementation Summary](docs/implementation/AMAZON_Q_IMPLEMENTATION_SUMMARY.md)
- [AWS Deployment Guide](docs/setup/AWS_DEPLOYMENT.md)
- [All Documentation](docs/README.md)

Security
========

For security best practices and recommendations, please see [SECURITY.md](SECURITY.md) and [Security Assessment](docs/assessment/SECURITY_ASSESSMENT.md).

**Note on jQuery**: ✅ **RESOLVED** - The bundled jQuery has been updated to v3.7.1 to patch the previously known XSS vulnerabilities (CVE-2020-11023 and CVE-2020-11022). The security vulnerabilities have been addressed.

Examples
========

### Basic Chat Usage
1. Start the server: `python runserver.py`
2. Share the generated `.onion` URL with participants
3. Open the URL in Tor Browser
4. Start chatting anonymously

### Email with PGP Encryption
1. Generate or import your PGP key (see [PGP Usage Guide](docs/user-guide/PGP_USAGE.md))
2. Configure email settings at `/email/config`
3. Compose encrypted email at `/email/compose`
4. Recipient automatically decrypts with their private key

### Burner Email System
1. Navigate to `/email/burner`
2. Click "Generate New Burner" to create temporary addresses
3. Manage multiple burner emails with live countdown timers
4. Copy addresses to clipboard for quick sharing

For more examples, see the documentation files in the repository.

Contributing
============

We welcome contributions to opsechat! Please see [Contributing Guide](docs/development/CONTRIBUTING.md) for guidelines on:
- How to submit issues
- How to propose changes
- Code style and standards
- Testing requirements
- Security considerations

License
=======

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

Copyright 2017 Hyperion Gray LLC

---

[![define hyperion gray](https://hyperiongray.s3.amazonaws.com/define-hg.svg)](https://www.hyperiongray.com/?pk_campaign=github&pk_kwd=dropchat "Hyperion Gray")
