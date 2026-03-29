# TUI Implementation TODO

This file tracks what needs to be done for the TUI chat system.

## ✅ COMPLETED (Phase 1: Basic TUI)

- [x] Create `src/tui/` directory structure
- [x] Implement basic TUI server (`src/tui/server.py`)
  - [x] In-memory message storage
  - [x] 4-minute message burn with overwriting
  - [x] Randomized username generation
  - [x] Text-only validation (max 1000 chars)
  - [x] Socket-based client/server communication
  - [x] Multi-threaded client handling
  - [x] Automatic cleanup thread
- [x] Implement basic TUI client (`src/tui/client.py`)
  - [x] urwid-based terminal interface
  - [x] Real-time message display
  - [x] Color-coded messages
  - [x] Input validation
  - [x] Automatic scrolling
- [x] Create launcher scripts
  - [x] `tui-server.py` - Server launcher
  - [x] `tui-client.py` - Client launcher
- [x] Add urwid dependency to `requirements.txt`
- [x] Basic testing and validation
- [x] Create TUI_README.md documentation

## 🔄 IN PROGRESS (Phase 2: Tor Integration)

- [ ] Integrate Tor hidden service in TUI server
  - [ ] Modify `src/tui/server.py` to support Tor
  - [ ] Add ephemeral hidden service creation
  - [ ] Display .onion address to share
  - [ ] Handle Tor connection failures gracefully
- [ ] Update client for Tor connections
  - [ ] Support connecting to .onion addresses
  - [ ] Add SOCKS proxy support
  - [ ] Connection status indicator

## 📋 TODO (Phase 3: Security & OpSec)

### Security Enhancements
- [ ] Add message sanitization improvements
  - [ ] Better b64 detection
  - [ ] Unicode/emoji filtering (if needed)
  - [ ] URL detection and handling
- [ ] Implement secure username sharing system
  - [ ] Generate shareable identity codes
  - [ ] Support for PGP key fingerprints
  - [ ] Standardized "who am I" system
- [ ] Add optional PGP encryption
  - [ ] Integrate PGP key management
  - [ ] Message encryption/decryption
  - [ ] Key exchange mechanism
  - [ ] Visual indicator for encrypted messages

### Message Management
- [ ] Implement message overwrite verification
  - [ ] Test memory overwriting actually works
  - [ ] Add optional wipe methods (zeros, random)
- [x] Add message rate limiting
  - [x] Prevent spam/flooding
  - [x] Per-user limits
  - [x] Configurable thresholds (10 msgs / 10s in `src/tui/server.py`)
- [ ] Improve message history management
  - [ ] Server-side message limit (not just client)
  - [ ] Memory usage monitoring
  - [ ] Graceful degradation under load

### User Experience
- [ ] Add status indicators
  - [ ] Connection status
  - [ ] Server health
  - [ ] Number of connected users
  - [ ] Time until message burn
- [ ] Improve error handling
  - [ ] Better error messages
  - [ ] Reconnection logic
  - [ ] Graceful degradation
- [ ] Add TUI features
  - [ ] Message timestamps (optional display)
  - [ ] Notification on new message
  - [ ] Scroll through history
  - [ ] Search messages (while they exist)

## 📋 TODO (Phase 4: Advanced Features)

### Multi-Room Support
- [ ] Implement room/channel system
  - [ ] Create/join rooms
  - [ ] Room-specific message lists
  - [ ] Room switching in TUI
  - [ ] Private vs public rooms

### Administration
- [ ] Add server admin commands
  - [ ] Kick users
  - [ ] Ban users (by IP or session)
  - [ ] Server stats
  - [ ] Force message burn
- [ ] Logging (optional, OpSec-aware)
  - [ ] Connection logs only (no messages)
  - [ ] Admin action logs
  - [ ] Security event logs
  - [ ] Log rotation and burning

### Performance
- [ ] Optimize message broadcasting
  - [ ] Batch messages
  - [ ] Reduce lock contention
  - [ ] Async I/O for clients
- [ ] Load testing
  - [ ] Test with 100+ users
  - [ ] Measure memory usage
  - [ ] Benchmark message throughput

## 🚫 NOT TODO (Out of Scope)

- ❌ Images - Never happening
- ❌ Video - Never happening
- ❌ File attachments - Not in chat (maybe later for email)
- ❌ Voice/audio - Not happening
- ❌ Persistent message storage - Defeats the purpose
- ❌ User registration/accounts - Ephemeral only
- ❌ Message editing - Burns are burns
- ❌ Read receipts - Privacy risk
- ❌ Typing indicators - Privacy risk
- ❌ User profiles - Privacy risk

## 📝 Notes

### Design Principles
1. **Privacy First**: Every feature must enhance or maintain privacy
2. **OpSec First**: Every feature must enhance or maintain operational security
3. **Simplicity**: Fewer features = fewer bugs = more secure
4. **Transparency**: Code should be easy to audit
5. **No Surprises**: Behavior should be predictable and documented

### Message Burning Rules
- **4 minutes**: Non-negotiable, no configuration
- **Overwrite**: Messages are overwritten before deletion
- **No recovery**: Once burned, gone forever
- **No exceptions**: System messages also burn

### Username Rules
- **Server-assigned**: No user choice
- **Random generation**: Adjective + Noun + 4-digit number
- **No reuse**: New username per session
- **No persistence**: Username dies with session

### Text-Only Rules
- **Max 1000 chars**: Prevents b64 image encoding
- **No HTML**: All special chars stripped
- **ASCII preferred**: Unicode support but monitored
- **No binary**: Text encoding only

## 🎯 Next Steps (Priority Order)

1. **Tor Integration** (HIGH) - Complete Phase 2
2. **PGP Encryption** (HIGH) - Add optional E2E encryption
3. **Security Testing** (HIGH) - Penetration testing, code review
4. **Multi-Room** (MEDIUM) - Support multiple chat rooms
5. **Admin Tools** (MEDIUM) - Basic moderation capabilities
6. **Performance** (LOW) - Only if issues arise

## 🔒 Security Considerations

### Current State
- ✅ In-memory only (no disk writes)
- ✅ Message burning (4 minutes)
- ✅ Message overwriting on delete
- ✅ Randomized usernames
- ✅ Text-only validation
- ⚠️ No E2E encryption yet (transport only via Tor)
- ⚠️ No authentication (ephemeral by design)
- ✅ Per-user message rate limiting enabled (10 messages / 10 seconds)

### Future Improvements
- Add PGP for E2E encryption
- Add rate limiting for spam prevention
- Consider adding captchas (for burner emails)
- Improve b64 detection
- Add timing attack mitigations

---

**Created**: 2026-02-26  
**Last Updated**: 2026-02-26  
**Status**: Phase 1 Complete, Phase 2 In Progress
