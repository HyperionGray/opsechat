# OpSecChat - Simple Web Chat Rooms

## Overview

OpSecChat now includes a simple, security-focused web-based chat room system designed for operational security communications. This system prioritizes security, simplicity, and reviewability over features.

## Key Features

- **Simple Room Creation**: Create secure chat rooms with a single command
- **E2E Encryption**: Optional end-to-end encryption using Web Crypto API
- **Terminal-Style UI**: Clean, minimal interface with no flashy elements
- **3-Minute Message Expiry**: Messages automatically delete after 3 minutes
- **Memory Overwriting**: Deleted messages are overwritten in memory
- **Randomized Usernames**: Color-coded for easy visual distinction
- **Text-Only**: No media, images, or file sharing
- **In-Memory Storage**: Zero disk writes
- **Tor Ready**: Works seamlessly with Tor hidden services

## Quick Start

### Creating a Local Chat Room

```bash
python chat-room.py
```

This will start a local server and display URLs like:
```
============================================================
💻 Local OpSecChat Server Started
============================================================

📍 Main URL: http://127.0.0.1:5000/[random-path]
💬 Chat Rooms: http://127.0.0.1:5000/chat
```

### Creating a Tor Hidden Service

```bash
# First, ensure Tor is running
tor --ControlPort 9051 --CookieAuthentication 1

# Then create the hidden service
python chat-room.py --tor
```

This will create a `.onion` address:
```
============================================================
🧅 Tor Hidden Service Created!
============================================================

📍 Main URL: http://[onion-address]/[random-path]
💬 Chat Rooms: http://[onion-address]/chat
```

### Custom Port

```bash
python chat-room.py --port 8080
```

## Using Chat Rooms

### Creating a Room

1. Navigate to `/chat` on your server
2. Click "Create New Chat Room"
3. Share the room URL with trusted contacts
4. Optionally enable E2E encryption in the room

### Joining a Room

1. Open the room URL shared with you
2. You'll be assigned a randomized username with a color
3. Type messages in the input box
4. Messages will appear for all users in the room

### Enabling E2E Encryption

1. In the chat room, toggle the "Encryption" switch
2. All your messages will be encrypted using AES-GCM
3. Other users must also enable encryption to read your messages
4. The encryption key is stored in your browser's sessionStorage
5. Keys are NOT shared - this is for protection against server compromise

**Important**: E2E encryption is per-user. If you want to chat with encrypted messages:
- All participants should enable encryption
- The encryption protects against server compromise
- Messages are still deleted after 3 minutes
- Encryption keys are session-only (lost when you close the tab)

## Security Features

### Message Expiry
- All messages are automatically deleted after **3 minutes**
- The timer starts when the message is sent
- Deleted messages are overwritten in memory before removal

### Memory Overwriting
When messages expire:
```python
# Message data is overwritten before deletion
msg["message"] = "X" * len(msg["message"])
msg["username"] = "X" * len(msg["username"])
```

This prevents memory forensics from recovering deleted messages.

### Room Expiry
- Rooms are automatically deleted after **1 hour** of inactivity
- All message data is overwritten before room deletion
- No persistent storage - everything is in-memory

### Username Randomization
- Usernames are server-generated and non-reusable
- Format: `[Adjective][Noun][4-digit-number]`
- Examples: `SilentWolf0423`, `GhostRaven7821`
- Each username is assigned a distinct color for easy identification

### Adaptive Write Throttling
- Write endpoints (`/chat/create`, `/chat/room/<id>/messages`, `/chat/dm/send`) now apply:
  - Per-session sliding-window limits
  - Progressive exponential backoff on repeated violations
  - `Retry-After` response header plus JSON `retry_after` guidance
- This keeps normal chat usage responsive while forcing abusive clients to slow down.

Environment variables (optional overrides):

```bash
OPSECHAT_RATE_CHAT_CREATE_MAX_REQUESTS=3
OPSECHAT_RATE_CHAT_CREATE_WINDOW_SECONDS=60
OPSECHAT_RATE_CHAT_MESSAGE_MAX_REQUESTS=30
OPSECHAT_RATE_CHAT_MESSAGE_WINDOW_SECONDS=60
OPSECHAT_RATE_DM_SEND_MAX_REQUESTS=5
OPSECHAT_RATE_DM_SEND_WINDOW_SECONDS=60
OPSECHAT_RATE_BACKOFF_BASE_SECONDS=5
OPSECHAT_RATE_BACKOFF_MULTIPLIER=2
OPSECHAT_RATE_BACKOFF_MAX_SECONDS=300
```

### E2E Encryption (Optional)
- Uses Web Crypto API (AES-GCM with 256-bit keys)
- Simple, reviewable JavaScript implementation
- No external dependencies beyond native browser APIs
- Encrypted messages are prefixed with 🔒 emoji
- Keys stored in sessionStorage (lost when tab closes)

## Technical Details

### API Endpoints

#### Create Room
```
POST /chat/create
Response: {"success": true, "room_id": "...", "room_url": "/chat/room/..."}
```

#### Get/Post Messages
```
GET  /chat/room/<room_id>/messages
POST /chat/room/<room_id>/messages
Body: {"message": "..."}
```

### Encryption Implementation

The E2E encryption uses native Web Crypto API:

```javascript
// Key generation
const key = await window.crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt", "decrypt"]
);

// Encryption
const iv = window.crypto.getRandomValues(new Uint8Array(12));
const encrypted = await window.crypto.subtle.encrypt(
    { name: "AES-GCM", iv: iv },
    key,
    encoded_message
);
```

This is **simple** and **reviewable** - only ~100 lines of JavaScript for the entire encryption system.

## Security Considerations

### What This Protects Against
- ✅ Server-side message logging
- ✅ Memory forensics (with overwriting)
- ✅ Long-term message retention
- ✅ Username correlation across sessions
- ✅ Network traffic analysis (when using Tor)

### What This Does NOT Protect Against
- ❌ Compromised client devices
- ❌ Man-in-the-middle attacks (use Tor + HTTPS)
- ❌ Malicious JavaScript injection (verify code)
- ❌ Screenshot/screen recording
- ❌ Keystroke logging

### Best Practices
1. **Use Tor Browser** - For maximum anonymity
2. **Verify Code** - Review the JavaScript before using
3. **Enable Encryption** - For additional protection
4. **Share Carefully** - Only share room URLs with trusted contacts
5. **Short Sessions** - Don't leave rooms open for extended periods
6. **No Sensitive Credentials** - Never share passwords or keys

## Comparison with Other Features

### Web Chat Rooms vs TUI
- **Web**: Browser-based, easier to use, E2E encryption option
- **TUI**: Terminal-only, no JavaScript, direct socket connection

### Web Chat vs Drop Chat
- **Web Rooms**: Multiple rooms, modern UI, E2E encryption
- **Drop Chat**: Single ephemeral chat, PGP support, legacy interface

Both are secure and suitable for operational security communications.

## Command Reference

```bash
# Start local server
python chat-room.py

# Start with Tor
python chat-room.py --tor

# Custom port
python chat-room.py --port 8080

# Bind to all interfaces (be careful!)
python chat-room.py --host 0.0.0.0

# Show help
python chat-room.py --help
```

## Troubleshooting

### "Tor Connection Failed"
Ensure Tor is running:
```bash
tor --ControlPort 9051 --CookieAuthentication 1
```

### "Room Not Found"
Rooms expire after 1 hour of inactivity. Create a new room.

### "Port Already in Use"
Use a different port:
```bash
python chat-room.py --port 8080
```

### Encryption Not Working
- Ensure both users have enabled encryption toggle
- Check browser console for errors
- Verify Web Crypto API is available (requires HTTPS or localhost)

## Code Review

The implementation is intentionally simple and reviewable:

- **simple_chat_routes.py** (~260 lines): Server-side logic
- **simple_chat_room.html** (~440 lines): Client-side UI and encryption
- **simple_chat_index.html** (~150 lines): Landing page

Total: ~850 lines of reviewable code for the entire system.

## License

MIT License - Same as the main OpSecChat project.

## Security Disclosure

If you find security vulnerabilities, please report them responsibly to the maintainers.
