# Production TODO List

**Last Updated:** March 18, 2026  
**Priority Order:** Critical → High → Medium → Low

---

## Recently Completed (2026-03)

- [x] Rate limiting on chat/create, chat/messages, and dm/send endpoints
- [x] `/health` endpoint returning JSON status with version and uptime
- [x] Domain rotation CLI and `domain_manager.py`
- [x] Simple web-based chat rooms (`simple_chat_routes.py`)
- [x] TUI server (`tui-server.py`) and client
- [x] In-memory message expiry with memory overwriting (3-min chat, 1-min DM)
- [x] Automated E2E encryption key exchange (`/chat/room/<id>/key`)
- [x] Security headers on every response (CSP, X-Frame-Options, etc.)
- [x] Structured logging / APM via `monitoring.py`
- [x] Test suite for `simple_chat_routes.py` (31 tests)
- [x] Fixed `datetime.utcnow()` deprecation – use `datetime.now(timezone.utc)`

---

## CRITICAL - Required Before Production (Blockers)

### 1. Architectural Decisions
- [ ] **DECIDE:** Authentication approach (External OAuth vs Ephemeral vs Encrypted Storage)
- [ ] **DECIDE:** Privacy vs Law Enforcement cooperation strategy
- [ ] **DECIDE:** Content restrictions enforcement method
- [ ] **DOCUMENT:** All decisions with rationale in `docs/architecture/DECISIONS.md`

### 2. User Authentication System (0% Complete)
- [ ] Choose authentication method (OAuth recommended)
- [ ] Implement user registration/signup page
- [ ] Implement login page
- [ ] Add session management
- [ ] Create user account database (or external service integration)
- [ ] Add password reset functionality (if applicable)
- [ ] Implement "remember me" functionality
- [ ] Test authentication flow end-to-end
- [ ] Security review of authentication code
**Estimated:** 10-15 days

### 3. Key Management UI (20% Complete)
- [ ] Create key management page (`/keys`)
- [ ] Add "Generate New Key" wizard with step-by-step guide
- [ ] Implement "Import Existing Key" form
- [ ] Add key display/view interface
- [ ] Implement key export/download functionality
- [ ] Add key deletion with confirmation
- [ ] Create educational modals:
  - [ ] "What are encryption keys?"
  - [ ] "Your key is generated in your browser"
  - [ ] "We cannot decrypt your messages"
  - [ ] "Save your key - we can't recover it"
- [ ] Build first-time user onboarding flow
- [ ] Add key backup reminders
- [ ] Test key generation/import/export thoroughly
**Estimated:** 7-10 days

### 4. User Dashboard & Navigation
- [ ] Create landing page with product selection
- [ ] Build user dashboard (`/dashboard`)
- [ ] Add navigation to:
  - [ ] Chat system
  - [ ] Email system
  - [ ] Burner email system
  - [ ] Key management
  - [ ] Account settings
- [ ] Implement plan/tier selection (free tier first)
- [ ] Add user onboarding tutorial
- [ ] Test all navigation paths
**Estimated:** 5-7 days

### 5. Legal Document Integration
- [ ] **CRITICAL:** Send AUP and ToS to legal counsel for review
- [ ] Incorporate legal feedback
- [ ] Create separate Privacy Policy document
- [ ] Add policy acceptance checkbox to signup flow
- [x] Create policy display pages (`/terms`, `/privacy`, `/aup`)
- [ ] Add policy links to all page footers
- [ ] Implement policy version tracking
- [ ] Add "Last Updated" dates to all policies
- [ ] Set effective dates
**Estimated:** 5-7 days (includes legal review time)

---

## HIGH PRIORITY - Required for Production

### 6. Abuse Prevention & Security
- [ ] Implement spam filtering (SpamAssassin or rspamd)
  - [ ] Install and configure spam filter
  - [ ] Set spam thresholds
  - [ ] Add bayesian learning
  - [ ] Test with spam corpus
- [x] Add rate limiting
  - [x] Implement per-session/IP limits (Flask-Limiter)
  - [x] Add per-endpoint throttling (`/chat/create`, `/chat/*/messages`, `/chat/dm/send`)
  - [ ] Configure reasonable thresholds (review after load testing)
  - [ ] Add backoff/retry logic
- [ ] Integrate second domain registrar API
  - [ ] Choose registrar (Namecheap recommended)
  - [ ] Implement API client
  - [ ] Update domain rotation logic
  - [ ] Test automated purchasing
- [ ] Add abuse detection
  - [ ] Keyword filtering
  - [ ] Pattern detection
  - [ ] Anomaly detection
  - [ ] Abuse scoring system
- [ ] Create abuse reporting interface
  - [ ] User reporting form
  - [ ] Admin review queue
  - [ ] Automated actions
  - [ ] Appeal process
**Estimated:** 10-12 days

### 7. Repository Organization (Violates Merge Rules!)
- [ ] Create `docs/` directory with subdirectories:
  - [ ] `docs/assessment/` - Move all assessment/review/summary files
  - [ ] `docs/setup/` - Move INSTALL, DOCKER, QUADLETS, AWS_DEPLOYMENT
  - [ ] `docs/user-guide/` - Move EMAIL_SYSTEM, PGP_USAGE, TESTING
  - [ ] `docs/development/` - Move CONTRIBUTING, MODERNIZATION
  - [ ] `docs/legal/` - Move ACCEPTABLE_USE_POLICY, TERMS_OF_SERVICE
  - [ ] `docs/implementation/` - Move IMPLEMENTATION_SUMMARY, ROADMAP files
- [ ] Create `VERSION` file with semantic version (start with `0.8.0-alpha`)
- [ ] Create `src/` directory and organize Python files:
  - [ ] `src/chat/` - Chat-related modules
  - [ ] `src/email/` - Email-related modules
  - [ ] `src/security/` - Security tools
  - [ ] `src/core/` - Core functionality
- [ ] Create `bin/` directory for executable scripts
- [ ] Create unified build system (pf-tasks or Makefile)
- [ ] Update all documentation cross-references
- [ ] Update import statements after moving files
- [ ] Test that everything still works after reorganization
**Estimated:** 2-3 days

### 8. Comprehensive Testing
- [x] Unit tests for `ChatRoom` class (messages, expiry, key generation, memory overwrite)
- [x] Unit tests for DM system (send, view, expiry, cleanup, memory overwrite)
- [x] Unit tests for secure ID generation (room IDs, DM IDs)
- [x] Unit tests for username/color generation
- [x] Unit tests for room cleanup (inactive > 1 hour)
- [x] API integration tests (create room, messages, key exchange, DM send/view)
- [x] Security headers tests (CSP, X-Frame-Options, Referrer-Policy, Server)
- [x] Message sanitization tests (XSS, length limits)
- [x] Per-session rate limiting tests (Flask-Limiter + in-memory sliding window)
- [x] Health endpoint tests
- [ ] Signup/login flow tests (blocked: auth not yet implemented)
- [ ] Key management UI tests (blocked: UI not yet implemented)
- [ ] Dashboard navigation tests (blocked: dashboard not yet implemented)
- [ ] Policy acceptance tests (blocked: legal pages not yet implemented)
- [ ] Spam filtering tests (blocked: spam filter not yet implemented)
- [ ] Load testing
  - [ ] Set up load testing framework (Locust or k6)
  - [ ] Create test scenarios
  - [ ] Run tests with 100-1000 concurrent users
  - [ ] Document performance limits
  - [ ] Optimize bottlenecks
- [ ] Security testing
  - [ ] Code review for vulnerabilities
  - [ ] Dependency scanning (partially done with Amazon Q)
  - [ ] Configuration review
  - [ ] Penetration testing
  - [ ] Consider third-party security audit
- [ ] Integration tests
  - [ ] Docker-based test infrastructure (test in container, not just host)
  - [ ] CI/CD pipeline integration for Python tests
  - [ ] Automated smoke tests post-deploy
**Estimated:** 3-5 days remaining (load + security + blocked items)

---

## MEDIUM PRIORITY - Important but Not Blocking

### 9. Production Infrastructure Hardening
- [ ] Document backup strategy (clarify what gets backed up)
- [ ] Create disaster recovery plan
- [ ] Test horizontal scaling
- [ ] Set up load balancer (nginx or HAProxy)
- [ ] Configure health check endpoints
- [ ] Test failover scenarios
- [ ] Add CDN for static assets (optional)
- [ ] Create production deployment guide
- [ ] Test AWS deployment end-to-end
**Estimated:** 3-5 days

### 10. Documentation Improvements
- [ ] Create `QUICKSTART.md` (5-minute getting started guide)
- [ ] Write admin/operator guide
- [ ] Create API documentation
- [ ] Write troubleshooting guide
- [ ] Create FAQ document
- [ ] Add screenshots to user guides
- [ ] Create deployment guide for other cloud providers (optional)
- [ ] Update README.md with production deployment info
**Estimated:** 7-10 days

### 11. GDPR & Privacy Compliance
- [ ] Add cookie consent banner (if needed)
- [ ] Implement data export functionality
- [ ] Implement data deletion mechanism
- [ ] Document legal basis for processing
- [ ] Add EU representative info (if serving EU users)
- [ ] Create data retention policy documentation
- [ ] Update Privacy Policy with GDPR requirements
**Estimated:** 3-4 days

### 12. Accessibility
- [x] ARIA labels added to chat room and chat index pages
- [ ] Screen reader testing
- [ ] Keyboard navigation testing
- [ ] WCAG 2.1 compliance check
- [ ] Color contrast verification
- [ ] Test with common accessibility tools
**Estimated:** 1-2 days remaining

---

## LOW PRIORITY - Nice to Have (Post-Launch)

### 13. File Attachment System
- [ ] Implement file upload (email only)
- [ ] Add file type validation (text-based only initially)
- [ ] Implement size limits
- [ ] Add MIME type checking
- [ ] Consider virus scanning integration
**Estimated:** 2-3 days

### 14. UI/UX Polish
- [ ] Consistent styling across all pages
- [ ] Mobile responsiveness improvements
- [ ] Loading spinners and progress indicators
- [ ] Better error messages
- [ ] Tooltips and help text
- [ ] Smooth animations/transitions
**Estimated:** 2-3 days

### 15. Additional Features (Future)
- [ ] Multiple language support (i18n)
- [ ] Video tutorials
- [ ] In-app help system
- [ ] User preferences/settings page
- [ ] Export chat history (encrypted)
- [ ] Additional domain registrar APIs (#3, #4, etc.)
- [ ] Advanced spam filtering (machine learning)
- [ ] User reputation system
- [ ] Paid tier implementation
**Estimated:** TBD

---

## COMPLETED ✅

### Capabilities Assessment & Tests (NEW - March 2026)
- [x] 56 new unit + integration tests in `tests/test_simple_chat.py`
  - [x] `ChatRoom` class: message lifecycle, auto-expiry, memory overwriting, unique keys
  - [x] DM system: send, view, expiry, cleanup, memory overwrite
  - [x] Secure ID generation: room IDs and DM IDs (uniqueness, length, URL-safety)
  - [x] Random username and color generation (format, variance)
  - [x] Room cleanup logic (inactive > 1 hour)
  - [x] `/chat/create` API endpoint
  - [x] `/chat/room/<id>/messages` GET + POST endpoint
  - [x] `/chat/room/<id>/key` automated key exchange endpoint
  - [x] `/chat/dm/send` and `/chat/dm/<id>` DM endpoints
  - [x] Security headers (CSP, X-Frame-Options, Referrer-Policy, Server suppression)
  - [x] Message sanitization and length limits
- [x] Updated TODO.md to reflect March 2026 state

### Simple Chat Rooms (March 2026)
- [x] Simple web-based chat room system
- [x] E2E encryption using Web Crypto API
- [x] Automated key exchange (room generates 256-bit AES key, no manual sharing)
- [x] Non-discoverable room IDs (32-byte `secrets.token_urlsafe`)
- [x] Terminal-style UI with minimal JavaScript
- [x] 3-minute message auto-delete with memory overwriting
- [x] Randomized usernames with color distinction
- [x] Room-based chat (create/join rooms)
- [x] Direct Messages (DM) for sharing room URLs — 1-minute expiry
- [x] Rate limiting: 10 creates/min, 30 messages/min, 5 DMs/min (per session)
- [x] CLI script for easy room creation (`chat-room.py`)
- [x] Comprehensive documentation in `docs/SIMPLE_CHAT_ROOMS.md`
- [x] E2E Playwright tests for new chat functionality
- [x] Tor hidden service support

### Repository Assessment
- [x] Comprehensive assessment of current state
- [x] Gap analysis for production readiness
- [x] Risk assessment
- [x] Cost estimation
- [x] Implementation roadmap

### Technical Foundation
- [x] Chat system with E2E encryption
- [x] Secure email system
- [x] Burner email system
- [x] PGP encryption integration
- [x] Tor hidden service integration
- [x] Zero-disk policy implementation
- [x] Containerization (Docker/Podman)
- [x] AWS deployment templates
- [x] Systemd quadlet support
- [x] 67+ passing unit tests (11 rate/health + 56 chat feature tests)

### Documentation (Exists but Needs Organization)
- [x] README.md
- [x] Security documentation
- [x] Email system documentation
- [x] Testing guide
- [x] Docker/deployment guides
- [x] AUP draft
- [x] ToS draft

### Security
- [x] jQuery updated to 3.7.1 (XSS fixes)
- [x] Input sanitization
- [x] Security tools (spoofing detection, phishing simulation)
- [x] Amazon Q code review integration
- [x] Content Security Policy (CSP) headers added
- [x] X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers added
- [x] Rate limiting on chat API endpoints (Flask-Limiter)

---

## Decision Log

### Pending Decisions (BLOCKER)
1. **Authentication Architecture** - Need to decide: External OAuth, Ephemeral, or Encrypted Storage
2. **Privacy vs LE Cooperation** - Need to decide: Accept limitation, Minimal logging, or Emergency logging
3. **Content Enforcement** - Need to decide: Technical, Policy, or Hybrid approach

### Made Decisions
- **Container Runtime:** Podman preferred over Docker ✅
- **Database:** Key-value store preferred over Postgres ✅
- **Build Tools:** pf.py preferred (but not yet implemented)
- **Documentation:** Must be in `docs/` directory ✅

---

## Notes

### Merge Blockers (From rules.json)
⚠️ **CRITICAL:** Repository currently violates merge requirements:
- Missing `docs/` directory - all documentation in root
- Missing `VERSION` file
- Missing unified build system
- Python files not organized in `src/`

**These MUST be fixed before merge per rules.json rule 07kwRDfGEGxIqlUsk3232**

### Time Estimates Summary
- **CRITICAL items:** 32-44 days
- **HIGH items:** 20-25 days (testing partially done)
- **MEDIUM items:** 14-21 days
- **LOW items:** 4-6 days
- **TOTAL:** ~70-96 days (single developer)

With 2-3 developers working in parallel: **6-8 weeks**

### Production Launch Checklist
Before announcing production launch, verify:
- [ ] All CRITICAL items completed
- [ ] All HIGH items completed
- [ ] Legal review completed
- [ ] Security audit completed
- [ ] Load testing passed
- [ ] Backup/recovery tested
- [ ] Documentation complete
- [ ] Support channels established
- [ ] Monitoring/alerting configured
- [ ] Incident response plan documented

---

**Created:** February 23, 2026  
**Last Updated:** March 18, 2026  
**Next Review:** After Phase 1 completion  
**Production Target:** April 6, 2026 (6 weeks)
