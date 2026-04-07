# OpSecChat TUI - Terminal User Interface Chat

**Privacy-focused, OpSec-first terminal chat system. No GUI, no nonsense.**

This is a serious privacy and opsec tool for serious privacy and opsec people. If you can't type 2 commands in the terminal, go download Telegram where they "totally swear you're private guys."

## Features

✅ **TUI Only** - Terminal interface, no web GUI bloat  
✅ **Privacy First** - All messages in-memory, burn after 4 minutes  
✅ **Randomized Usernames** - Server-assigned, no "Jerry Here" problem  
✅ **Text Only** - No images, no video, no b64 encoded garbage  
✅ **Message Validation** - Max 1000 chars, prevents b64 image encoding  
✅ **Server Rate Limiting** - 20 messages per 60 seconds per client  
✅ **Secure Deletion** - Messages overwritten before removal  
✅ **Zero Disk** - Nothing touches disk except the application code  
✅ **Tor Integration** - Full support for Tor hidden services (.onion)  
✅ **SOCKS Proxy** - Client supports connecting via Tor SOCKS proxy  

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# For Tor integration (optional but recommended)
sudo apt-get install tor  # or your package manager
```

### 1. Start the Server (with Tor)

```bash
# Start Tor daemon first
tor --ControlPort 9051 --CookieAuthentication 1

# In another terminal, start server with Tor
python tui-server.py --tor

# Output will show:
# [*] Creating ephemeral hidden service...
# [*] Hidden service created: abc123...xyz.onion
# 🧅 Tor Hidden Service: abc123...xyz.onion
# 📡 Local Server: 127.0.0.1:5555
```

### 2. Start the Server (without Tor - testing)

```bash
# Local testing only
python tui-server.py

# Bind to all interfaces
python tui-server.py --host 0.0.0.0 --port 5555
```

### 3. Connect with Client

```bash
# Connect to local server (no Tor)
python tui-client.py

# Connect to Tor hidden service
python tui-client.py --host abc123...xyz.onion --port 5555

# Connect via Tor SOCKS proxy (for .onion or extra privacy)
python tui-client.py --host <server> --port 5555 --tor

# Specify custom Tor SOCKS port
python tui-client.py --host <server> --port 5555 --tor --tor-port 9050
```

The client will automatically use Tor SOCKS proxy if:
- The hostname ends with `.onion`, OR
- You specify `--tor` flag

### 4. Chat!

- Type your message and press **Enter** to send
- Press **Ctrl+C** to quit
- Your username is randomly assigned (e.g., `PhantomRaven4523`)
- Messages automatically disappear after 4 minutes

## Privacy & Security Features

### In-Memory Only
All messages are stored **only in RAM**. Nothing is written to disk. When the server stops, all data is gone.

### Message Burning (4 Minutes)
Messages automatically delete after 4 minutes. When deleted, the message content is **overwritten** with 'X' characters before removal (prevents memory recovery).

### Randomized Usernames
No user choice on usernames. Server assigns random names like:
- `SwiftWolf2341`
- `PhantomHawk7823`
- `ShadowViper1234`

This prevents:
- Username reuse across sessions
- Identification through username patterns
- The "Jerry Here" problem

### Text-Only Enforcement
- Max 1000 characters per message
- HTML/special characters stripped
- Detects and rejects likely b64-encoded data
- **No images, no video, no binary data**

### Tor Integration

The server can create an **ephemeral Tor hidden service** (.onion address):
- New .onion address each time server starts
- No configuration files on disk
- Tor handles all encryption
- Server accessible only via Tor network

The client supports:
- Direct connections (testing)
- .onion address connections (via SOCKS proxy)
- Force Tor for any connection (extra anonymity)

**Prerequisites for Tor:**
1. Tor daemon running with ControlPort (server)
2. Tor SOCKS proxy running on port 9050 (client)

```bash
# Start Tor with ControlPort (for server)
tor --ControlPort 9051 --CookieAuthentication 1

# Or use system Tor (usually has SOCKS on 9050 by default)
sudo systemctl start tor
```

## Message Limits & Rules

- **Max message length**: 1000 characters
- **Message lifetime**: 4 minutes (240 seconds)
- **Max chat history**: 200 messages in client (memory management)
- **No images**: Text only, no exceptions
- **No video**: Text only, no exceptions
- **No b64 encoding**: Large base64-like strings are rejected
- **Rate limit**: 20 messages per 60 seconds per connected client

## Architecture

```
┌─────────────┐         Socket (JSON)        ┌─────────────┐
│ TUI Client  │────────────────────────────▶│ TUI Server  │
│  (urwid)    │                              │  (Python)   │
└─────────────┘◀────────────────────────────┘─────────────┘
                  Real-time messages
```

### Server
- Multi-threaded socket server
- In-memory message storage
- Background cleanup thread (runs every 10s)
- Broadcasts messages to all connected clients
- JSON protocol for client/server communication

### Client
- urwid-based TUI (terminal UI framework)
- Separate thread for receiving messages
- Real-time message display
- Color-coded messages (your messages vs others)

## Development

### Running Tests

```bash
# Test server functionality
python -c "from src.tui.server import ChatServer; s = ChatServer(); print(s.generate_username())"

# Test imports
python -c "from src.tui import client, server; print('✓ Imports OK')"
```

### Code Structure

```
src/tui/
├── __init__.py      # Package init
├── server.py        # Chat server (socket-based)
└── client.py        # Chat client (urwid TUI)
```

## Comparison: TUI vs Web UI

| Feature | TUI (This) | Web UI (Old) |
|---------|-----------|--------------|
| Privacy | ✅ Better | ⚠️ Cookies, sessions |
| Simplicity | ✅ Simple | ⚠️ Complex |
| Security | ✅ No JS attacks | ⚠️ XSS, CSRF risks |
| Disk Usage | ✅ None | ⚠️ Templates, static files |
| Opsec | ✅ Terminal only | ⚠️ Browser fingerprinting |
| User-friendly | ⚠️ CLI only | ✅ Point & click |

## FAQ

### Why TUI instead of Web UI?

This is a **serious privacy/opsec tool for serious people**. If you need privacy:
- No browser fingerprinting
- No JavaScript attack surface  
- No cookies or tracking
- No web server vulnerabilities
- Terminal = simple = fewer bugs = more secure

### Can I use images?

**No.** Text only. This prevents:
- Horrible content being hosted
- Metadata leaks (EXIF)
- Steganography attacks
- Large data transfers

### Can I choose my username?

**No.** Usernames are randomized by the server. This prevents:
- Username reuse across sessions
- Identification patterns
- Social engineering

### How do I identify myself to people I know?

Use a **standardized phrase or code** that only you and your contact know. For example:
- "The eagle flies at midnight"
- "Project Phoenix status: green"
- A shared PGP key fingerprint

**Do NOT say** "Jerry Here" or use your real name.

### What happens to messages after 4 minutes?

Messages are:
1. Overwritten with 'X' characters (prevents memory recovery)
2. Removed from the message list
3. Gone forever (in-memory only, no disk)

### Can I extend the 4-minute timer?

**No.** This is by design. Messages burn after 4 minutes, **no negotiation, no config**. If you need longer persistence, this tool is not for you.

## Coming Soon

- [ ] Full Tor hidden service integration
- [ ] PGP encryption support (optional)
- [ ] Multi-room support
- [ ] Message signing/verification
- [ ] Improved standardized identity system

## Security Notes

⚠️ **Important:**
- This tool is for **legitimate privacy needs**
- **No illegal content** - See [ACCEPTABLE_USE_POLICY.md](docs/legal/ACCEPTABLE_USE_POLICY.md)
- Messages are ephemeral but not end-to-end encrypted by default
- Use PGP for maximum security (coming soon)
- Always use Tor Browser or Tor network for anonymity

## Support

Having issues? 

1. Check you have `urwid` installed: `pip install urwid>=2.1.0`
2. Check Python version: `python --version` (need 3.8+)
3. Check server is running before starting client
4. Try `--host 127.0.0.1` explicitly if connection fails

## License

MIT License - See [LICENSE.md](LICENSE.md)

---

**Remember:** This is opsec first. Privacy first. No images, no video, no b64 garbage. Text only. Messages burn. Stay safe.
