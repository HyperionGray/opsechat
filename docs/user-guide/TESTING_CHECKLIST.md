# Testing Checklist - OpSecHat v0.8.0

Use this checklist to verify all new features are working correctly.

---

## ✅ Pre-Deployment Tests

### 1. Unit Tests
```bash
cd /path/to/opsechat
python3 test_new_features.py
```
**Expected**: All 6 tests pass
- [ ] ✅ Secure ID generation
- [ ] ✅ Automated key exchange
- [ ] ✅ Rate limiting
- [ ] ✅ Base64 detection
- [ ] ✅ Message length caps
- [ ] ✅ DM functionality

### 2. Security Scan
```bash
# CodeQL scan (automated in CI/CD)
# Or run manually if available
```
**Expected**: 0 vulnerabilities
- [ ] ✅ No security alerts

### 3. Import Verification
```bash
python3 -c "
from simple_chat_routes import *
from email_system import *
from domain_manager import *
print('All imports OK')
"
```
**Expected**: "All imports OK" with no errors
- [ ] ✅ All modules import successfully

---

## 🧪 Functional Tests

### Test 1: Automated Key Exchange

**Steps:**
1. Start server: `python runserver.py test`
2. Create room: `curl -X POST http://localhost:5001/chat/create`
3. Note the `room_id` from response
4. Fetch key: `curl http://localhost:5001/chat/room/{room_id}/key`

**Expected Results:**
- [ ] Room created successfully
- [ ] Room ID is long (>40 chars) and URL-safe
- [ ] Key endpoint returns `encryption_key` field
- [ ] Key is base64-encoded string

**Example:**
```json
// Create room response
{
  "success": true,
  "room_id": "wWR_qXjnWQlr4oXqlR2JLxA...",
  "room_url": "/chat/room/wWR_qXjnWQlr4oXqlR2JLxA..."
}

// Get key response
{
  "room_id": "wWR_qXjnWQlr4oXqlR2JLxA...",
  "encryption_key": "5A5EjM+s7+6Mf92w7Hpu..."
}
```

---

### Test 2: Direct Messages (DM)

**Steps:**
1. Send DM:
```bash
curl -X POST http://localhost:5001/chat/dm/send \
  -H "Content-Type: application/json" \
  -d '{"room_id": "test123", "message": "Join the secure room!"}'
```
2. Note the `dm_id` from response
3. View DM immediately: `curl http://localhost:5001/chat/dm/{dm_id}`
4. Wait 65 seconds
5. Try to view again: `curl http://localhost:5001/chat/dm/{dm_id}`

**Expected Results:**
- [ ] DM created with unique dm_id
- [ ] Immediate viewing succeeds (within 60s)
- [ ] Viewing after 60s returns "DM expired" error
- [ ] DM disappears from storage

**Example:**
```json
// Send DM response
{
  "success": true,
  "dm_id": "14gvVa4l3SPsLJc1Ijb_sA",
  "dm_url": "/chat/dm/14gvVa4l3SPsLJc1Ijb_sA",
  "expires_in": 60
}

// View DM response (within 60s)
{
  "dm_id": "14gvVa4l3SPsLJc1Ijb_sA",
  "sender_name": "SilentWolf4523",
  "room_id": "test123",
  "message": "Join the secure room!",
  "expires_in": 45
}

// View DM response (after 60s)
{
  "error": "DM expired"
}
```

---

### Test 3: Rate Limiting

**Steps:**
1. Start Python shell:
```python
from email_system import burner_manager

user_id = "test_user_001"

# Send 10 emails (the limit)
for i in range(10):
    allowed, msg = burner_manager.check_send_rate_limit(user_id)
    if allowed:
        burner_manager.record_sent_email(user_id)
        print(f"Email {i+1} sent")

# Try to send 11th email
allowed, msg = burner_manager.check_send_rate_limit(user_id)
print(f"11th email allowed: {allowed}")
print(f"Message: {msg}")

# Check status
status = burner_manager.get_send_limit_status(user_id)
print(f"Status: {status}")
```

**Expected Results:**
- [ ] First 10 emails send successfully
- [ ] 11th email is blocked
- [ ] Error message mentions "Rate limit exceeded"
- [ ] Status shows 10/10 used, 0 remaining

---

### Test 4: Message Length Caps

**Test in Browser or via API:**

**Chat Message (500 char limit):**
```bash
# Create message with 501 chars
MSG=$(python3 -c "print('A' * 501)")
curl -X POST http://localhost:5001/chat/room/{room_id}/messages \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MSG\"}"
```

**Expected Results:**
- [ ] Message rejected
- [ ] Error: "Message too long. Maximum 500 characters allowed."

**DM Message (200 char limit):**
```bash
# Create message with 201 chars
MSG=$(python3 -c "print('A' * 201)")
curl -X POST http://localhost:5001/chat/dm/send \
  -H "Content-Type: application/json" \
  -d "{\"room_id\": \"test\", \"message\": \"$MSG\"}"
```

**Expected Results:**
- [ ] DM rejected
- [ ] Error: "DM too long. Maximum 200 characters."

---

### Test 5: Base64 Detection

**Test in Browser or via API:**
```bash
# Try to send a long string with no spaces (simulates base64)
MSG=$(python3 -c "print('A' * 150)")
curl -X POST http://localhost:5001/chat/room/{room_id}/messages \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MSG\"}"
```

**Expected Results:**
- [ ] Message rejected
- [ ] Error: "Invalid message format. Only plain text allowed."
- [ ] Error message doesn't reveal detection mechanism

---

### Test 6: Domain Rotation CLI

**Steps:**
1. Configure (skip if no real API key):
```bash
python domain_rotation_cli.py config
# Enter test values or real Porkbun API credentials
```

2. Check status:
```bash
python domain_rotation_cli.py status
```

3. Search for domains:
```bash
python domain_rotation_cli.py search --max-price 3 --limit 3
```

4. Validate non-interactive mode:
```bash
python domain_rotation_cli.py rotate --yes --max-attempts 10
python domain_rotation_cli.py rotate-auto --dry-run --json
```

**Expected Results:**
- [ ] Config saved to `~/.opsechat/domain_config.json`
- [ ] Status shows budget and owned domains
- [ ] Search finds available cheap domains (if configured)
- [ ] `rotate --yes` skips interactive prompt
- [ ] `rotate-auto --dry-run --json` returns machine-readable output and exits 0

**Note**: Actual rotation requires real API credentials and budget.

---

### Test 7: Security Warnings

**Test in Browser:**
1. Open chat room in browser: `http://localhost:5001/chat/room/{room_id}`
2. Check for security warning modal

**Expected Results:**
- [ ] Security warning modal appears on first visit
- [ ] Warning mentions "NO MEDIA SHARING"
- [ ] Warning mentions "VIOLATIONS = CONSEQUENCES"
- [ ] User must click "I UNDERSTAND AND AGREE" to proceed
- [ ] Input is disabled until warning accepted
- [ ] Warning doesn't show again in same session

---

### Test 8: XSS Protection

**Test in Browser or via API:**
```bash
# Try to send message with HTML/JavaScript
curl -X POST http://localhost:5001/chat/room/{room_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "<script>alert(\"XSS\")</script>Hello"}'
```

**Expected Results:**
- [ ] Message is sanitized
- [ ] HTML tags removed
- [ ] No script execution in browser
- [ ] Special characters encoded (`<` → `&lt;`, etc.)

---

## 🚀 Deployment Tests

### Test 9: Systemd Auto-Restart

**Steps:**
1. Install quadlets: `./install-quadlets.sh`
2. Start service: `systemctl --user start opsechat-app`
3. Check status: `systemctl --user status opsechat-app`
4. Kill the container: `podman kill opsechat-app`
5. Wait 10 seconds
6. Check status again: `systemctl --user status opsechat-app`

**Expected Results:**
- [ ] Service starts successfully
- [ ] Service shows "active (running)"
- [ ] After kill, service auto-restarts within 5 seconds
- [ ] Service remains "active (running)"
- [ ] Logs show restart in journalctl

---

### Test 10: Health Checks

**Steps:**
1. Check Tor container health:
```bash
podman healthcheck run opsechat-tor
systemctl --user status opsechat-tor
```

**Expected Results:**
- [ ] Health check passes
- [ ] Tor container shows "healthy"
- [ ] Control port (9051) is accessible

---

## 📊 Integration Tests

### Test 11: End-to-End Chat Flow

**Steps:**
1. User A creates room
2. User A sends DM to User B with room ID
3. User B views DM (within 60s)
4. User B joins room
5. Both users enable encryption (automatic key fetch)
6. Users exchange encrypted messages
7. Wait 3 minutes
8. Verify old messages disappeared

**Expected Results:**
- [ ] Room creation successful
- [ ] DM delivery successful
- [ ] DM expires after 60s
- [ ] Both users can join room
- [ ] Encryption enabled automatically for both
- [ ] Encrypted messages decrypt correctly
- [ ] Messages auto-delete after 3 minutes

---

### Test 12: Email Rate Limiting Integration

**Steps:**
1. Configure email settings (if available)
2. Try to send 11 emails in quick succession
3. Check rate limit status

**Expected Results:**
- [ ] First 10 emails send
- [ ] 11th email blocked
- [ ] User sees clear error message
- [ ] Status shows quota usage
- [ ] Receiving emails still works (unlimited)

---

## 🎯 Acceptance Criteria

All tests above should pass. Mark each test as complete:

### Core Functionality
- [ ] ✅ Automated key exchange works
- [ ] ✅ DMs expire in 1 minute
- [ ] ✅ Rate limiting enforced
- [ ] ✅ Message length caps work
- [ ] ✅ Base64 detection works

### Security
- [ ] ✅ XSS protection effective
- [ ] ✅ Security warnings display
- [ ] ✅ Secure IDs generated
- [ ] ✅ Memory overwriting occurs
- [ ] ✅ No security vulnerabilities

### Deployment
- [ ] ✅ Auto-restart works
- [ ] ✅ Health checks pass
- [ ] ✅ Systemd integration works
- [ ] ✅ Containers start properly

### Documentation
- [ ] ✅ README updated
- [ ] ✅ NEW_FEATURES.md created
- [ ] ✅ IMPLEMENTATION_SUMMARY.md created
- [ ] ✅ API documented

---

## 🐛 Troubleshooting

### If Tests Fail

**Import errors:**
```bash
pip install Flask stem
```

**Module not found:**
```bash
# Ensure you're in the correct directory
cd /path/to/opsechat
python3 test_new_features.py
```

**API tests fail:**
```bash
# Ensure server is running
python runserver.py test
# In another terminal, run tests
```

**Systemd tests fail:**
```bash
# Reload systemd
systemctl --user daemon-reload
# Check logs
journalctl --user -u opsechat-app -n 50
```

---

## ✅ Sign-Off

Once all tests pass, mark complete:

- [ ] All unit tests passed
- [ ] All functional tests passed
- [ ] All deployment tests passed
- [ ] All integration tests passed
- [ ] All acceptance criteria met

**Tested by**: ________________  
**Date**: ________________  
**Status**: ✅ READY FOR PRODUCTION / ⚠️ NEEDS FIXES

---

**Last Updated**: March 2, 2026  
**Version**: 0.8.0-alpha
