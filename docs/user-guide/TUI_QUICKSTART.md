# TUI Chat Quick Start Guide

This guide will get you up and running with the OpSecChat TUI in under 5 minutes.

## What You Need

- Python 3.8 or higher
- Terminal/Command line access
- (Optional) Tor daemon for hidden service support

## Installation

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat
pip install -r requirements.txt
```

This installs:
- `urwid` - Terminal UI framework
- `PySocks` - SOCKS proxy support for Tor
- `stem` - Tor control library
- Other dependencies

### 2. Verify Installation

```bash
# Test imports
python -c "import urwid, socks, stem; print('✓ All dependencies installed')"
```

## Quick Test (No Tor)

### Terminal 1: Start Server

```bash
python bin/tui-server.py
```

You should see:
```
============================================================
📡 Local Server: 127.0.0.1:5555
============================================================

[*] OpSecChat TUI Server running on 127.0.0.1:5555
[*] Messages burn after 240 seconds
[*] Max message length: 1000 chars
[*] Press Ctrl+C to stop
```

### Terminal 2: Connect Client

```bash
python bin/tui-client.py
```

You'll see the TUI interface:
```
┌────────────────────────────────────────────────────────┐
│    OpSecChat TUI - Privacy First | Messages burn in    │
│         4 min | Text only - No images/video            │
├────────────────────────────────────────────────────────┤
│                                                        │
│  * Welcome! You are ShadowFox3421. Messages burn in   │
│    4 minutes.                                          │
│                                                        │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ >>> [Type your message here]                           │
└────────────────────────────────────────────────────────┘
 Enter: Send | Ctrl+C: Quit | Your username: ShadowFox3421
```

### Chat!

1. Type a message in the input box
2. Press **Enter** to send
3. Messages appear in the main window
4. Press **Ctrl+C** to quit

**Try opening multiple clients** to test multi-user chat!

## Production Use (With Tor)

For anonymous, encrypted communication over Tor:

### 1. Install and Start Tor

```bash
# Install Tor (Ubuntu/Debian)
sudo apt-get install tor

# Start Tor with ControlPort
tor --ControlPort 9051 --CookieAuthentication 1
```

Leave this running in the background.

### 2. Start Server with Tor

```bash
python bin/tui-server.py --tor
```

Output:
```
[*] Starting with Tor integration...
[*] Creating ephemeral hidden service, this may take a minute or two
[*] Hidden service created: abc123def456ghi789.onion

============================================================
🧅 Tor Hidden Service: abc123def456ghi789.onion
📡 Local Server: 127.0.0.1:5555
============================================================
```

**Share the .onion address** with your contacts.

### 3. Connect via Tor

Your contacts use:

```bash
python bin/tui-client.py --host abc123def456ghi789.onion --port 5555
```

The client automatically detects `.onion` and uses Tor SOCKS proxy.

## Features You Get

### ✅ Privacy Features
- **In-Memory Only** - Nothing written to disk
- **4-Minute Burn** - Messages auto-delete with overwriting
- **Randomized Usernames** - No username reuse
- **Text Only** - No images, videos, or encoded data
- **Tor Support** - Anonymous communication

### ✅ Security Features
- **Message Validation** - Max 1000 chars
- **Secure Deletion** - Overwrite before delete
- **No Configuration Files** - Ephemeral by design
- **No Logs** - Zero persistence

### ⚠️ Limitations (By Design)
- **No Message History** - Messages burn after 4 minutes
- **No File Sharing** - Text only
- **No Username Choice** - Server assigns random names
- **No Persistence** - Nothing saved to disk

## Troubleshooting

### "Connection Refused"

**Problem:** Client can't connect to server

**Solution:**
1. Make sure server is running
2. Check firewall settings
3. Verify port 5555 is not in use: `lsof -i :5555`

### "Tor Connection Failed"

**Problem:** Server can't create hidden service

**Solution:**
1. Check Tor is running: `ps aux | grep tor`
2. Verify ControlPort 9051 is accessible
3. Check Tor logs: `journalctl -u tor`

### "Module Not Found: socks"

**Problem:** PySocks not installed

**Solution:**
```bash
pip install PySocks>=1.7.1
```

### "Module Not Found: urwid"

**Problem:** urwid not installed

**Solution:**
```bash
pip install urwid>=2.1.0
```

### "Address Already in Use"

**Problem:** Port 5555 is in use

**Solution:**
```bash
# Find process using port
lsof -i :5555
# Kill it or use different port
python bin/tui-server.py --port 5556
```

## Advanced Usage

### Custom Port

```bash
# Server
python bin/tui-server.py --port 6666

# Client
python bin/tui-client.py --port 6666
```

### Bind to All Interfaces

```bash
python bin/tui-server.py --host 0.0.0.0 --port 5555
```

**Warning:** Only do this if you understand the security implications!

### Force Tor for Regular Connections

```bash
# Use Tor even for non-.onion addresses
python bin/tui-client.py --host <server-ip> --tor
```

### Custom Tor SOCKS Port

```bash
# If your Tor SOCKS is on different port
python bin/tui-client.py --host <server> --tor-port 9150
```

## Testing

### Automated Test

```bash
# Run automated test
python tests/test-tui-client.py

# Should output:
# [✓] Connected to server
# [✓] Received welcome
# [✓] Sent test message
# [✓] Test completed successfully!
```

### Manual Test

1. Start server: `python bin/tui-server.py`
2. Open 3 terminals with clients
3. Send messages from different clients
4. Verify all clients see the messages
5. Wait 4+ minutes, verify messages disappear

## Next Steps

- Read [TUI_README.md](TUI_README.md) for full documentation
- Read [TUI TODO](../development/TUI_TODO.md) for planned features
- Report issues on GitHub
- Contribute improvements

## Security Reminders

⚠️ **Important:**
- **Share .onion addresses securely** - Don't post them publicly
- **Use Tor Browser** for additional anonymity
- **No illegal content** - See Acceptable Use Policy
- **Messages are ephemeral** - Don't rely on them persisting
- **Backup important info** - Messages will be deleted

---

**Questions?** Check [TUI_README.md](TUI_README.md) or open an issue on GitHub.

**Ready to chat?** Just run `python bin/tui-server.py` and you're live!
