# Product Release TODO

**Last Updated:** March 2, 2026  
**Status:** Post-Release Enhancements

---

## Critical Items for Full Production Release

### 1. Automatic Key Exchange (HIGH PRIORITY)

**Current State:** Manual PGP key import required  
**Desired State:** Automatic, secure key exchange

**Options:**
1. **Signal Protocol** (Recommended)
   - Industry-proven double ratchet algorithm
   - Perfect forward secrecy
   - Automatic key rotation
   - Library: `libsignal-protocol-python`

2. **ECDH Key Exchange**
   - Simpler implementation
   - Elliptic curve Diffie-Hellman
   - Can use existing crypto libraries

3. **Noise Protocol Framework**
   - Modern, secure handshake patterns
   - Used by WireGuard, Signal

**Implementation Steps:**
- [ ] Choose protocol (Signal Protocol recommended)
- [ ] Install required libraries
- [ ] Implement key exchange handshake
- [ ] Add to TUI client/server
- [ ] Test key exchange flow
- [ ] Update documentation
- [ ] Add automated tests

**Estimated Effort:** 5-7 days

---

### 2. Domain Rotation CLI Tool

**Current State:** Implemented (`domain_rotation_cli.py` and compatibility wrapper `rotate-domain.py`)  
**Desired State:** Continue hardening and UX improvements

**Created:** `rotate-domain.py`

```bash
# Usage examples:
python rotate-domain.py --search
python rotate-domain.py --buy example.xyz --years 1
python rotate-domain.py --list-owned
python rotate-domain.py --get-pricing xyz
```

**Implementation:**
- [x] Create CLI argument parser
- [x] Add interactive mode
- [x] Display pricing before purchase
- [x] Confirm purchases with user
- [x] Add budget checking
- [x] Store API credentials securely
- [x] Add to documentation
- [x] Add state persistence for owned domains and datetime fields
- [ ] Add optional custom max-price and retry flags

**Estimated Effort:** 1-2 days

---

### 3. Enhanced Key Management UX

**Current Issues:**
- Keys stored in browser localStorage (can be lost)
- No backup reminders
- No key recovery mechanism
- Unclear key status

**Improvements:**
- [ ] Add key backup/export wizard
- [ ] Show key fingerprints
- [ ] Add "Last backed up" timestamp
- [ ] Backup reminders after N days
- [ ] Key recovery instructions
- [ ] Visual key status dashboard
- [ ] Test coverage

**Estimated Effort:** 3-4 days

---

## Medium Priority Enhancements

### 4. Inline Help System

**Add to TUI:**
- [ ] `/help` command - show all commands
- [ ] `/status` - show server/connection status
- [ ] `/users` - show connected users (count only)
- [ ] `/quit` - graceful disconnect
- [ ] `/encrypt <on|off>` - toggle encryption

**Estimated Effort:** 1 day

---

### 5. Improved Error Messages

**Current State:** Technical error messages  
**Desired State:** User-friendly explanations with solutions

**Examples:**
- "Connection refused" → "Could not connect to server. Is it running?"
- "Decryption failed" → "Could not decrypt message. Check your private key."
- "Invalid message" → "Message too long (max 1000 characters)"

**Implementation:**
- [ ] Audit all error messages
- [ ] Create error code mapping
- [ ] Add helpful suggestions
- [ ] Test error scenarios

**Estimated Effort:** 2 days

---

### 6. Connection Status Indicator

**Add to TUI:**
- Show connection status
- Show encryption status
- Show Tor status (if applicable)
- Show message count / burn time

**UI Example:**
```
[🟢 Connected] [🔒 Encrypted] [🧅 Tor] [15 msgs, 3:45 until burn]
```

**Estimated Effort:** 1-2 days

---

## Low Priority (Nice to Have)

### 7. Multi-Room Support

Allow multiple chat rooms on same server.

**Features:**
- [ ] Room creation
- [ ] Room joining/leaving
- [ ] Room list
- [ ] Per-room message history

**Estimated Effort:** 3-5 days

---

### 8. Message Signing/Verification

Add cryptographic signatures to verify message authenticity.

**Features:**
- [ ] Sign messages with private key
- [ ] Verify signatures with public key
- [ ] Visual indicator for signed messages
- [ ] Warning for unsigned messages

**Estimated Effort:** 2-3 days

---

### 9. Export Chat History (Encrypted)

Allow users to export chat history in encrypted format.

**Features:**
- [ ] Export as encrypted JSON
- [ ] Password-protected export
- [ ] Import encrypted history
- [ ] Auto-delete after export

**Estimated Effort:** 2 days

---

### 10. Rate Limiting

Prevent spam and abuse.

**Features:**
- [ ] Per-user message rate limit
- [ ] Configurable limits
- [ ] Exponential backoff
- [ ] Abuse detection

**Estimated Effort:** 1-2 days

---

### 11. Headful Test Runner

**Create:** `run-headed-tests.sh`

```bash
#!/bin/bash
# Run Playwright tests in headed mode (visible browser)
export DISPLAY=:0
npx playwright test --config=playwright-release.config.js --headed --project=chromium-headed
```

**Note:** Currently tests run in headless mode for CI compatibility

**Estimated Effort:** 1 hour

---

## Testing Enhancements

### 12. Integration Tests

**Current:** Unit tests and manual tests  
**Needed:** Automated integration tests

**Test Scenarios:**
- [ ] Full TUI client-server connection
- [ ] Message send/receive flow
- [ ] Key exchange workflow
- [ ] Burner email generation
- [ ] Domain purchase simulation
- [ ] Tor hidden service creation

**Estimated Effort:** 3-4 days

---

### 13. Performance Testing

**Test:**
- [ ] Server with 100+ concurrent connections
- [ ] Message throughput
- [ ] Memory usage over time
- [ ] Message cleanup performance
- [ ] Database query performance (if added)

**Tools:**
- Locust or k6 for load testing
- Memory profiler

**Estimated Effort:** 2-3 days

---

## Documentation Updates

### 14. Video Tutorials

**Create:**
- [ ] Quick start video (5 minutes)
- [ ] PGP encryption setup
- [ ] Burner email usage
- [ ] Domain rotation tutorial

**Estimated Effort:** 2-3 days

---

### 15. API Documentation

**Create:**
- [ ] OpenAPI/Swagger spec
- [ ] API reference documentation
- [ ] Code examples for each endpoint
- [ ] Authentication guide (when added)

**Estimated Effort:** 2 days

---

### 16. Troubleshooting Guide

**Create comprehensive guide:**
- [ ] Common connection issues
- [ ] Tor configuration problems
- [ ] Encryption/decryption errors
- [ ] Installation problems
- [ ] Platform-specific issues

**Estimated Effort:** 1 day

---

## Known Limitations

### Items NOT Planned (By Design)

1. **Persistent Storage:** Messages intentionally not saved to disk
2. **User Accounts:** Intentionally anonymous, no registration
3. **Message Editing:** Would break encryption chain
4. **Read Receipts:** Privacy concern
5. **User List:** Privacy concern (only show count)
6. **File Attachments:** Abuse/privacy risk (text only)

---

## Timeline Estimate

**High Priority (Critical for Full Release):** 9-13 days
- Automatic key exchange: 5-7 days
- Domain CLI: 1-2 days
- Key management UX: 3-4 days

**Medium Priority:** 7-10 days
- Inline help: 1 day
- Error messages: 2 days
- Status indicator: 1-2 days
- Multi-room: 3-5 days

**Low Priority:** 8-12 days
- Message signing: 2-3 days
- Chat export: 2 days
- Rate limiting: 1-2 days
- Integration tests: 3-4 days
- Performance tests: 2-3 days

**Total Estimate:** 24-35 days (single developer)  
**With 2 developers:** 12-18 days

---

## Next Steps

1. Prioritize automatic key exchange implementation
2. Create domain rotation CLI tool
3. Enhance key management UX
4. Add integration tests
5. Update documentation with new features

---

**Last Updated:** March 2, 2026  
**Next Review:** After key exchange implementation  
**Maintained By:** Development Team
