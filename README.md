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

This provides AWS ECS Fargate deployment with Tor integration, network isolation, and comprehensive security monitoring. See [AWS Deployment Guide](aws/AWS_DEPLOYMENT_GUIDE.md) for complete instructions.

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

That's it! The script will handle everything. See [DOCKER.md](DOCKER.md) for full documentation.

### Podman Quadlets (systemd integration)

For production deployments with systemd integration:

```bash
$ git clone git@github.com:HyperionGray/opsechat.git
$ cd opsechat
$ podman build -t localhost/opsechat:latest .
$ ./install-quadlets.sh
$ systemctl --user start opsechat-app
```

See [QUADLETS.md](QUADLETS.md) for full documentation.

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
- **Automated Domain Purchasing** - Porkbun API integration for cheap domain rotation (.xyz, .club, etc.) - see [DOMAIN_REGISTRAR_API.md](DOMAIN_REGISTRAR_API.md)
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

Security & Code Quality
=======================

## Amazon Q Code Review Integration ✅

This project includes comprehensive Amazon Q Code Review integration with automated security scanning, performance optimization, and architecture validation.

### Automated Security Scanning
- **Continuous Monitoring**: GitHub Actions workflow runs security scans on every push and pull request
- **Multi-Tool Analysis**: Bandit, Safety, Semgrep, and CodeQL for comprehensive coverage
- **Custom Rules**: OpSecChat-specific security rules for Tor and PGP handling
- **Zero Vulnerabilities**: All critical and high-severity issues have been addressed

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
- [Amazon Q Implementation Summary](AMAZON_Q_IMPLEMENTATION_SUMMARY.md)
- [AWS Deployment Guide](aws/AWS_DEPLOYMENT_GUIDE.md)
- [Amazon Q Integration Guide](aws/AMAZON_Q_INTEGRATION_GUIDE.md)
- [Repository Secrets Guide](aws/REPOSITORY_SECRETS_GUIDE.md)

Security
========

For security best practices and recommendations, please see [SECURITY.md](SECURITY.md).

**Note on jQuery**: ✅ **RESOLVED** - The bundled jQuery has been updated to v3.7.1 to patch the previously known XSS vulnerabilities (CVE-2020-11023 and CVE-2020-11022). The security vulnerabilities have been addressed.

Examples
========

### Basic Chat Usage
1. Start the server: `python runserver.py`
2. Share the generated `.onion` URL with participants
3. Open the URL in Tor Browser
4. Start chatting anonymously

### Email with PGP Encryption
1. Generate or import your PGP key (see [PGP_USAGE.md](PGP_USAGE.md))
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

We welcome contributions to opsechat! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
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
