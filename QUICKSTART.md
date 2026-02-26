# OpSecChat Quick Start Guide

Get started with OpSecChat in 5 minutes! This guide covers the fastest path to running your first secure, anonymous chat session.

## Prerequisites

- Linux machine (any distribution)
- Tor Browser installed
- Docker/Podman installed (recommended) OR Python 3.8+

## Quick Start (Recommended: Docker/Podman)

### Step 1: Clone and Start

```bash
# Clone the repository
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat

# Start with one command!
./compose-up.sh
```

That's it! The script will:
- Build the container
- Start Tor daemon
- Launch OpSecChat server
- Display your unique .onion URL

### Step 2: Access Your Chat

Look for output like this:
```
[*] Started a new hidden service with the address of:
    abc123def456ghi789jkl.onion/secret-path-xyz123
```

### Step 3: Share and Chat

1. Open **Tor Browser**
2. Navigate to your `.onion` URL
3. Share the URL with your chat partners
4. Start chatting securely and anonymously!

## Alternative: Native Installation

If you prefer running without containers:

```bash
# Clone repository
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start Tor Browser (must be running)
# Then start OpSecChat
python runserver.py
```

## What You Get

✅ **Anonymous Chat** - Your identity is hidden via Tor  
✅ **Ephemeral Service** - New .onion address every run  
✅ **Encrypted Communication** - All traffic encrypted via Tor  
✅ **No Persistence** - Messages disappear after 3 minutes  
✅ **PGP Support** - Optional end-to-end encryption (see below)

## Using PGP Encryption (Optional)

For maximum security, enable PGP encryption:

1. Enable JavaScript in Tor Browser (for your .onion only)
2. Visit Settings → NoScript → Whitelist your .onion address
3. Click "Enable Encryption" in the chat interface
4. Generate a new key or import existing key
5. Share your public key with chat partners

See [PGP Usage Guide](docs/user-guide/PGP_USAGE.md) for detailed instructions.

## Using Email Features

OpSecChat includes a secure email system:

1. Navigate to `/email` on your .onion URL
2. Configure SMTP/IMAP (optional) at `/email/config`
3. Generate burner emails at `/email/burner`
4. Send encrypted emails with PGP support

See [Email Quick Start](docs/user-guide/EMAIL_QUICKSTART.md) for more details.

## Common Issues

### "Tor Connection Failed"

**Solution:** Ensure Tor Browser is running or Tor daemon is accessible on port 9051.

```bash
# Check if Tor is running
ps aux | grep tor

# Start Tor daemon if needed
sudo systemctl start tor
```

### "Port Already in Use"

**Solution:** Another service is using port 5000 or the Tor port.

```bash
# Find what's using port 5000
sudo lsof -i :5000

# Kill the process or choose different port
PORT=5001 python runserver.py
```

### "Module Not Found"

**Solution:** Install dependencies in virtual environment.

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Container Won't Start

**Solution:** Check Docker/Podman is running and you have permissions.

```bash
# For Podman
systemctl --user start podman
podman ps

# For Docker
sudo systemctl start docker
sudo docker ps
```

## Next Steps

Now that you have OpSecChat running, explore these features:

- **[Email System](docs/user-guide/EMAIL_SYSTEM.md)** - Send secure, anonymous emails
- **[Burner Emails](docs/user-guide/EMAIL_SYSTEM.md#burner-email-system)** - Generate temporary email addresses
- **[PGP Encryption](docs/user-guide/PGP_USAGE.md)** - Advanced end-to-end encryption
- **[Testing](docs/user-guide/TESTING.md)** - Run the test suite
- **[AWS Deployment](docs/setup/AWS_DEPLOYMENT.md)** - Deploy to the cloud
- **[Contributing](docs/development/CONTRIBUTING.md)** - Help improve OpSecChat

## Security Reminders

⚠️ **Important Security Notes:**

- **No Persistent Storage** - Messages are deleted after 3 minutes
- **Ephemeral Services** - New .onion address each time you run the server
- **Share Carefully** - Only share your .onion URL with trusted contacts
- **Use Tor Browser** - Always access via Tor Browser for anonymity
- **Backup Keys** - If using PGP, backup your private keys securely
- **No Nefarious Use** - See [Acceptable Use Policy](docs/legal/ACCEPTABLE_USE_POLICY.md)

## Need Help?

- **Documentation**: [docs/README.md](docs/README.md)
- **Full README**: [README.md](README.md)
- **Security Info**: [SECURITY.md](SECURITY.md)
- **Report Issues**: [GitHub Issues](https://github.com/HyperionGray/opsechat/issues)

## Stopping the Server

### Docker/Podman
```bash
./compose-down.sh
```

### Native
Press `Ctrl+C` in the terminal running `runserver.py`

---

**That's it!** You now have a secure, anonymous chat server running on the Tor network. 🎉

For more advanced features and configuration options, see the [full documentation](docs/README.md).

---

**Version:** 0.8.0-alpha  
**Last Updated:** February 23, 2026  
**License:** MIT
