# New Features Guide - OpSecHat v0.8.0

This guide covers the new features added in the final push for OpSecHat production readiness.

## 🔑 Automated Key Exchange

### What Changed
Previously, users had to manually share encryption keys. Now, each chat room automatically generates and distributes a shared encryption key when users join.

### How It Works
1. When a room is created, a cryptographically secure 256-bit AES key is generated
2. When users join the room and enable encryption, the key is automatically fetched from the server
3. All participants in the room use the same key for E2E encryption

### Usage
```javascript
// Users simply enable encryption - the key is fetched automatically
1. Join a chat room
2. Click "Enable Encryption" toggle
3. The room key is automatically downloaded
4. All encrypted messages are automatically decrypted
```

### Security Considerations
- The key is transmitted over Tor's encrypted connection
- Each room has a unique key
- Keys are ephemeral - they're destroyed when the room expires (1 hour)
- Room IDs are now 32-byte cryptographically secure tokens (non-discoverable)

---

## 💬 Direct Messages (DM)

### Purpose
Simple, ephemeral messaging for sharing room IDs with specific users. DMs are designed for one purpose: **sharing chat room URLs securely**.

### Features
- **Read-once retrieval** - DM is deleted immediately after first successful view
- **1-minute expiry** - Unread messages disappear after 60 seconds
- **Simple text only** - Max 200 characters
- **Memory overwriting** - Data is overwritten before deletion
- **Non-discoverable** - Cryptographically secure DM IDs

### API Usage

#### Send a DM
```bash
POST /chat/dm/send
Content-Type: application/json

{
  "room_id": "wWR_qXjnWQlr4oXqlR2JLxA...",
  "message": "Join me in the secure room: /chat/room/wWR_qXjnWQlr4oXqlR2JLxA..."
}

Response:
{
  "success": true,
  "dm_id": "14gvVa4l3SPsLJc1Ijb_sA",
  "dm_url": "/chat/dm/14gvVa4l3SPsLJc1Ijb_sA",
  "expires_in": 60
}
```

#### View a DM (one-time read)
```bash
GET /chat/dm/{dm_id}

Response:
{
  "dm_id": "14gvVa4l3SPsLJc1Ijb_sA",
  "sender_name": "SilentWolf4523",
  "room_id": "wWR_qXjnWQlr4oXqlR2JLxA...",
  "message": "Join me in the secure room...",
  "expires_in": 45
}
```

### Example Workflow
```python
# User A creates a room
POST /chat/create
→ Gets room_id: "abc123..."

# User A sends DM to User B with room ID
POST /chat/dm/send
{
  "room_id": "abc123...",
  "message": "Secret meeting at /chat/room/abc123..."
}
→ Gets dm_id: "xyz789"

# User A shares DM URL with User B out-of-band
# User B accesses the DM (single successful read)
GET /chat/dm/xyz789
→ Gets room ID and joins the chat

# Any second read fails
GET /chat/dm/xyz789
→ {"error": "DM not found or expired"}
```

---

## 🔒 Enhanced Security Features

### Message Length Caps
- **Chat messages**: 500 characters maximum
- **DM messages**: 200 characters maximum
- **Purpose**: Prevent base64 encoding of images/videos

### Base64 Detection
Automatic detection and blocking of potential encoded content:
- Messages with <5% spaces and >100 characters are flagged
- Users get clear error: "Message appears to contain encoded data. Only plain text allowed."

### XSS Protection
All user input is now properly sanitized:
```javascript
// HTML tags removed
message = message.replace(/<[^>]+>/g, '');

// Special characters encoded
message = message
  .replace('&', '&amp;')
  .replace('<', '&lt;')
  .replace('>', '&gt;')
  .replace('"', '&quot;')
  .replace("'", '&#x27;');
```

### Security Warning Modal
First-time users see a prominent security warning:
- **NO MEDIA SHARING** - Strictly text only
- **NO ABUSE** - Clear consequences for violations
- **VIOLATIONS = CONSEQUENCES** - Logs preserved, not burned, potential reporting
- Users must click "I UNDERSTAND AND AGREE" before chatting

---

## 📧 Email Rate Limiting

### Purpose
Prevent spam and abuse while allowing legitimate use (receiving emails for service sign-ups).

### Limits
- **Sending**: 10 emails per hour
- **Receiving**: Unlimited (main use case)
- **Reset**: Hourly rolling window

### Implementation
```python
# Check if user can send
allowed, error_msg = burner_manager.check_send_rate_limit(user_id)
if not allowed:
    return error(error_msg)

# Record the send
burner_manager.record_sent_email(user_id)

# Check status
status = burner_manager.get_send_limit_status(user_id)
# Returns: {sends_used: 3, sends_remaining: 7, max_sends_per_hour: 10}
```

### User Experience
When composing email, users see:
```
Rate Limit Status: 3/10 emails sent this hour
Remaining: 7 emails
```

When limit exceeded:
```
❌ Rate limit exceeded. You can send 10 emails per hour. Try again in 42 minutes.
```

---

## 🌐 Domain Rotation CLI

### Purpose
Easy domain rotation for burner email service to avoid domain bans and maintain service availability.

### Installation
```bash
# The CLI is included in the main repository
chmod +x domain_rotation_cli.py
```

### Configuration
```bash
# Configure API credentials
python domain_rotation_cli.py config

# You'll be prompted for:
# - Porkbun API Key
# - Porkbun API Secret
# - Monthly Budget (default: $50)
```

### Usage

#### Check Current Status
```bash
python domain_rotation_cli.py status

Output:
=== Domain Rotation Status ===

Active Domain: abc123xyz.club

Budget:
  Monthly: $50.00
  Spent: $2.99
  Remaining: $47.01

Domains Owned: 1

✅ Current burner email domain: abc123xyz.club
   Configure your email system to use: user@abc123xyz.club
```

#### Search for Available Domains
```bash
python domain_rotation_cli.py search

Output:
=== Searching for Available Cheap Domains ===

Searching for domains under $5...

Attempt 1/5...
  ✅ Found: m8kl2p9x.xyz - $0.99
Attempt 2/5...
  ✅ Found: 7h3n5k2q.club - $1.99
...
```

#### Rotate to New Domain
```bash
python domain_rotation_cli.py rotate

Output:
=== Domain Rotation ===

Monthly Budget: $50.00
Current Spending: $2.99
Remaining: $47.01
Domains Owned: 1

Searching for available cheap domain...

Found: n5x8q2k7.xyz for $0.99

Proceed with purchase? (yes/no): yes

Purchasing domain...

✅ Successfully purchased and activated: n5x8q2k7.xyz
```

#### List Owned Domains
```bash
python domain_rotation_cli.py list

Output:
=== Owned Domains ===

1. abc123xyz.club
   Price: $2.99
   Purchased: 2026-03-01 14:23
   Expires: 2027-03-01

2. n5x8q2k7.xyz [ACTIVE]
   Price: $0.99
   Purchased: 2026-03-02 10:15
   Expires: 2027-03-02
```

### Integration with Burner Email
After rotating domains, update your email configuration:
1. Run `python domain_rotation_cli.py status` to get active domain
2. Configure DNS records for the new domain
3. Update email server settings to use new domain
4. Old burner emails will continue working until their domain expires

### Budget Management
- Set monthly budget to prevent overspending
- CLI tracks spending automatically
- Prevents purchases that would exceed budget
- Resets monthly (manual reset required)

---

## 🚀 Production Deployment

### Systemd Auto-Restart
The systemd units now include robust auto-restart configuration:

```ini
[Service]
# Auto-restart policy - keep service running at all times
Restart=always
RestartSec=5
# Maximum restart attempts (0 = infinite)
StartLimitBurst=0
# Stop timeout - give time for graceful shutdown
TimeoutStopSec=60
# Health check settings
TimeoutStartSec=120
```

### Benefits
- **Automatic recovery** from crashes
- **Infinite retries** - never gives up
- **Graceful shutdown** - 60 second timeout for cleanup
- **Health checks** - Validates service is responding

### Deployment
```bash
# Build image
podman build -t localhost/opsechat:latest .

# Install quadlets
./install-quadlets.sh

# Start services
systemctl --user start opsechat-app

# Check status
systemctl --user status opsechat-app
systemctl --user status opsechat-tor

# View logs
journalctl --user -u opsechat-app -f
```

### Monitoring
The systemd units provide:
- Automatic log rotation via journald
- Health checks every 10 seconds
- Restart on failure with exponential backoff
- Integration with system monitoring tools

---

## 🔐 Cryptographic Security Improvements

### Room ID Generation
**Before:**
```python
room_id = id_generator(size=16)  # Using random.choice()
```

**After:**
```python
room_id = secrets.token_urlsafe(32)  # Cryptographically secure
```

**Impact:**
- Room IDs are now non-discoverable
- 256 bits of entropy (vs ~95 bits before)
- Safe for security-critical applications
- Complies with cryptographic best practices

### Session ID Generation
**Before:**
```python
session["_id"] = id_generator(size=16)  # Weak randomness
```

**After:**
```python
session["_id"] = generate_secure_dm_id()  # Uses secrets module
```

### Automated Encryption Key Generation
Each chat room gets a unique 256-bit AES-GCM key:
```python
self.room_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
```

---

## 📋 Migration Guide

### For Existing Users

#### Chat System
No migration needed. New rooms will automatically use:
- Cryptographically secure IDs
- Automated key exchange
- Enhanced security warnings

Old room URLs will NOT work after upgrade (ephemeral anyway).

#### Email System
1. Configure rate limiting (automatic)
2. Add security warnings to templates (done)
3. Optional: Set up domain rotation CLI

#### Deployment
1. Update quadlet files: `cp quadlets/* ~/.config/containers/systemd/`
2. Reload systemd: `systemctl --user daemon-reload`
3. Restart services: `systemctl --user restart opsechat-app`

---

## 🧪 Testing

### Test Automated Key Exchange
```bash
# Terminal 1: Start server
python runserver.py test

# Terminal 2: Create room and check key endpoint
curl http://localhost:5001/{path}/chat/create -X POST
curl http://localhost:5001/chat/room/{room_id}/key
```

### Test Rate Limiting
```python
from email_system import burner_manager

user_id = "test_user"

# Send 10 emails
for i in range(10):
    allowed, msg = burner_manager.check_send_rate_limit(user_id)
    if allowed:
        burner_manager.record_sent_email(user_id)
        print(f"Email {i+1} sent")

# Try 11th email
allowed, msg = burner_manager.check_send_rate_limit(user_id)
assert not allowed, "Should be rate limited"
print(f"Rate limited: {msg}")
```

### Test DM Feature
```bash
# Send DM
curl -X POST http://localhost:5001/chat/dm/send \
  -H "Content-Type: application/json" \
  -d '{"room_id": "test123", "message": "Join me!"}'

# View DM (within 60 seconds)
curl http://localhost:5001/chat/dm/{dm_id}

# Wait 61 seconds and try again (should be expired)
sleep 61
curl http://localhost:5001/chat/dm/{dm_id}
```

---

## 📚 Additional Resources

- **Security Guide**: See SECURITY.md for security best practices
- **Deployment Guide**: See docs/setup/ for deployment options
- **API Reference**: See docs/api/ for complete API documentation
- **Contributing**: See docs/development/CONTRIBUTING.md

---

## ⚠️ Important Security Notes

1. **Room IDs are sensitive** - Treat them as secrets, share only over secure channels
2. **DMs are ephemeral and read-once** - Screenshot or save important room IDs before opening/expiry
3. **Rate limits are per-user** - Each session has independent limits
4. **Domain rotation requires DNS** - New domains need proper DNS configuration
5. **Auto-restart is aggressive** - Monitor logs for repeated crashes

---

**Last Updated**: March 2, 2026
**Version**: 0.8.0-alpha
**Author**: OpSecHat Development Team
