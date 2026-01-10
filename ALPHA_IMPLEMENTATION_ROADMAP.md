# Alpha Release Implementation Roadmap

**Created:** January 6, 2026  
**Updated:** January 8, 2026  
**Target Alpha Release:** [TBD]  
**Current Status:** ~73% Complete  
**Estimated Time to Alpha:** 3-4 weeks with focused effort

---

## Overview

This document provides a detailed implementation roadmap for bringing opsechat to alpha release, based on the comprehensive assessment in ALPHA_READINESS_ASSESSMENT.md.

**NEW:** Tasks have been organized into **4 parallel work streams** to maximize development velocity. Each group can be worked on independently by different developers or teams.

---

## 🚀 Parallel Work Streams (Critical Path)

The following 4 groups contain tasks that can be executed in parallel. Each group is independent and has minimal dependencies on the others until final integration.

### 🟦 Group 1: User Authentication & Account Management (3-4 days)

**Team Focus:** Backend authentication, session management, user data structures

**Core Tasks:**
- [ ] Design ephemeral user storage system (`UserManager` class in `user_manager.py`)
  - [ ] In-memory user dictionary structure: `{username: {password_hash, created_at, session_id, key_fingerprint}}`
  - [ ] Password hashing with bcrypt/argon2
  - [ ] Session token generation and validation
  - [ ] Automatic cleanup of stale sessions (24hr timeout)
- [ ] Create signup page template (`templates/signup.html`)
  - [ ] Username field with validation (alphanumeric, 3-20 chars)
  - [ ] Password field with strength indicator
  - [ ] Password confirmation field
  - [ ] Policy acceptance checkboxes (ToS, AUP)
  - [ ] Accessible form design
  - [ ] CAPTCHA integration (optional for alpha)
- [ ] Create login page template (`templates/login.html`)
  - [ ] Username/password fields
  - [ ] "Remember me" option (browser storage)
  - [ ] Error messaging for invalid credentials
  - [ ] Link to signup page
  - [ ] Rate limiting display (lockout after 5 failed attempts)
- [ ] Implement `/signup` route in `runserver.py`
  - [ ] Validate username uniqueness
  - [ ] Validate password strength (min 12 chars, mixed case, numbers, symbols)
  - [ ] Check policy acceptance
  - [ ] Create user session
  - [ ] Redirect to dashboard on success
- [ ] Implement `/login` route in `runserver.py`
  - [ ] Authenticate credentials
  - [ ] Create session cookie (httpOnly, secure, sameSite)
  - [ ] Rate limiting (max 5 attempts per 15min per IP)
  - [ ] Redirect to dashboard on success
- [ ] Implement `/logout` route in `runserver.py`
  - [ ] Clear session data
  - [ ] Remove from active sessions
  - [ ] Clear browser cookies
  - [ ] Redirect to landing page
- [ ] Add `@require_auth` decorator for protected routes
  - [ ] Check session validity
  - [ ] Verify session not expired
  - [ ] Redirect to login if not authenticated
- [ ] Update existing routes to require authentication
  - [ ] `/chats` → requires auth
  - [ ] `/email` → requires auth
  - [ ] `/burner` → requires auth (or session-only for anonymous)
- [ ] Add CSRF protection
  - [ ] Generate CSRF tokens
  - [ ] Validate on POST/PUT/DELETE
  - [ ] Add to all forms
- [ ] Create password strength validator
  - [ ] Minimum length check (12 chars)
  - [ ] Complexity requirements (upper, lower, number, symbol)
  - [ ] Common password dictionary check
  - [ ] Visual strength indicator
- [ ] Write comprehensive unit tests (`tests/test_user_manager.py`)
  - [ ] Test user creation
  - [ ] Test duplicate username rejection
  - [ ] Test password hashing (never stored in plain)
  - [ ] Test session creation/validation
  - [ ] Test session expiration
  - [ ] Test login rate limiting
  - [ ] Test CSRF protection

**Files to Create/Modify:**
- `NEW: user_manager.py` (200-300 lines)
- `NEW: templates/signup.html` (100-150 lines)
- `NEW: templates/login.html` (80-100 lines)
- `MODIFY: runserver.py` - Add auth routes and decorators (50-100 lines added)
- `NEW: tests/test_user_manager.py` (150-200 lines)

**Testing Strategy:**
- Unit tests for all authentication logic
- Manual testing: signup → login → access protected route → logout → verify no access
- Test session expiration
- Test rate limiting
- Test CSRF protection

---

### 🟩 Group 2: UI/UX & Key Management (4-5 days)

**Team Focus:** Frontend, user experience, PGP key management, educational content

**Core Tasks:**
- [ ] Design new landing page (`templates/landing_new.html`)
  - [ ] Hero section with tagline: "Private, Encrypted Communication Over Tor"
  - [ ] Feature highlights (Chat, Email, Burner Emails)
  - [ ] Security promises (E2E encryption, zero-disk, ephemeral)
  - [ ] CTA buttons: "Sign Up Free" and "Learn More"
  - [ ] Responsive design (mobile-first)
- [ ] Create user dashboard (`templates/dashboard.html`)
  - [ ] Welcome message with username
  - [ ] Three main product cards:
    - [ ] 💬 Encrypted Chat - "Start chatting securely"
    - [ ] 📧 Secure Email - "Send encrypted emails"
    - [ ] 🔥 Burner Emails - "Create temporary addresses"
  - [ ] Key status indicator (has key ✅ / no key ⚠️)
  - [ ] Quick links: Settings, Key Management, Logout
  - [ ] Usage stats (messages sent, emails, burners active)
- [ ] Implement `/dashboard` route in `runserver.py`
  - [ ] Require authentication
  - [ ] Load user data (key status, usage stats)
  - [ ] Render dashboard template
- [ ] Create plan selection interface (`templates/plan_selection.html`)
  - [ ] Free tier highlighted (default for alpha)
    - [ ] "Free Forever" badge
    - [ ] Features: 100 messages/day, 50 emails/day, 5 burners
    - [ ] "Start Free" button
  - [ ] Paid tiers (grayed out - "Coming Soon")
    - [ ] Pro plan ($5/month) - Higher limits
    - [ ] Enterprise plan ($20/month) - Unlimited
  - [ ] Feature comparison table
  - [ ] FAQ section: "What's included?"
- [ ] Create key generation wizard (`templates/key_wizard.html`)
  - [ ] Modal-based workflow (4 steps)
  - [ ] Step 1: Introduction
    - [ ] "Encryption protects your privacy"
    - [ ] "Generate your PGP key pair now"
    - [ ] Educational tooltip: What is PGP?
  - [ ] Step 2: Key generation options
    - [ ] Radio buttons: "Generate new key" (default) vs "Import existing"
    - [ ] Name/email fields (optional, for key metadata)
    - [ ] Key strength selector (2048-bit default, 4096-bit option)
  - [ ] Step 3: Generation progress
    - [ ] Progress spinner with message "Generating in your browser..."
    - [ ] Educational note: "This happens client-side only"
    - [ ] Real-time generation using OpenPGP.js
  - [ ] Step 4: Success and backup
    - [ ] ✅ "Key generated successfully!"
    - [ ] Display public key (read-only textarea)
    - [ ] Display key fingerprint
    - [ ] 🔑 "Download Private Key" button (secure export)
    - [ ] ⚠️ Warning: "Save this key - we cannot recover it for you"
    - [ ] "I've saved my key" checkbox (required to proceed)
- [ ] Create key management page (`templates/key_management.html`)
  - [ ] Current key status section
    - [ ] Display: "Active Key" or "No Key Installed"
    - [ ] Key fingerprint (if exists)
    - [ ] Creation date
    - [ ] Last backup timestamp
  - [ ] Public key display (read-only, copyable)
  - [ ] Key actions
    - [ ] Export private key button
    - [ ] Import key interface (file upload + paste)
    - [ ] Delete key (with confirmation modal)
    - [ ] Backup reminder notification
  - [ ] Key health indicators
    - [ ] Key strength score
    - [ ] Expiration date (if set)
    - [ ] Usage stats (messages encrypted)
- [ ] Create onboarding flow (`templates/onboarding.html`)
  - [ ] First-time user modal (shown after signup)
  - [ ] Multi-step tutorial:
    - [ ] Welcome screen
    - [ ] Key generation prompt
    - [ ] Tour of dashboard
    - [ ] How to send encrypted message
    - [ ] Security best practices
  - [ ] "Skip tour" option (with reminder)
  - [ ] Progress indicator (step 1 of 5)
- [ ] Enhance `static/pgp-manager.js`
  - [ ] `generateKeyPair()` function
    - [ ] Accept name, email, passphrase
    - [ ] Use OpenPGP.js to generate
    - [ ] Return public/private keys
    - [ ] Store in localStorage
  - [ ] `importKey()` function
    - [ ] Validate PGP key format
    - [ ] Parse and verify key
    - [ ] Store in localStorage
    - [ ] Show success/error feedback
  - [ ] `exportPrivateKey()` function
    - [ ] Retrieve from localStorage
    - [ ] Format for download
    - [ ] Trigger browser download
    - [ ] Warn about security
  - [ ] `deleteKey()` function
    - [ ] Confirmation dialog
    - [ ] Clear from localStorage
    - [ ] Update UI state
  - [ ] Key strength calculator
    - [ ] Check key length (2048/4096)
    - [ ] Check algorithm
    - [ ] Display strength score
  - [ ] Backup reminder system
    - [ ] Check last backup timestamp
    - [ ] Show reminder if >30 days
    - [ ] Snooze option
- [ ] Create educational tooltips system
  - [ ] Tooltip component (CSS + JS)
  - [ ] Help icons next to complex features
  - [ ] Tooltips for:
    - [ ] "What is E2E encryption?"
    - [ ] "Why do I need a key?"
    - [ ] "How do burner emails work?"
    - [ ] "What is Tor?"
    - [ ] "What data do you store?"
  - [ ] Dismissible and persistent preferences
- [ ] Add breadcrumb navigation
  - [ ] Dashboard > Chat
  - [ ] Dashboard > Email > Compose
  - [ ] Dashboard > Settings > Key Management
  - [ ] Consistent across all pages
- [ ] Implement responsive design
  - [ ] Mobile breakpoints (320px, 768px, 1024px)
  - [ ] Touch-friendly buttons (min 44px)
  - [ ] Readable font sizes (16px base)
  - [ ] Collapsible navigation menu
- [ ] Write E2E tests for UI flows (`tests/ui-dashboard.spec.js`)
  - [ ] Test: Complete signup flow
  - [ ] Test: Generate new key
  - [ ] Test: Navigate to chat from dashboard
  - [ ] Test: Navigate to email from dashboard
  - [ ] Test: Export and re-import key
  - [ ] Test: Mobile responsive layout

**Files to Create/Modify:**
- `NEW: templates/landing_new.html` (150-200 lines)
- `NEW: templates/dashboard.html` (100-150 lines)
- `NEW: templates/plan_selection.html` (120-150 lines)
- `NEW: templates/key_wizard.html` (200-250 lines)
- `NEW: templates/key_management.html` (150-180 lines)
- `NEW: templates/onboarding.html` (100-120 lines)
- `MODIFY: static/pgp-manager.js` - Add UI integration (200-300 lines added)
- `NEW: static/key-management.css` (150-200 lines)
- `NEW: static/dashboard.css` (100-150 lines)
- `MODIFY: runserver.py` - Add dashboard and key routes (30-50 lines added)
- `NEW: tests/ui-dashboard.spec.js` (150-200 lines)

**Testing Strategy:**
- Playwright E2E tests for all user flows
- Manual testing in Tor Browser
- Test on multiple screen sizes
- Accessibility testing (screen readers, keyboard navigation)
- User testing with 3-5 beta testers

---

### 🟥 Group 3: Security & Abuse Prevention (4-5 days)

**Team Focus:** Spam filtering, rate limiting, abuse detection, API integrations

**Core Tasks:**
- [ ] Research and select spam filter solution
  - [ ] Option 1: SpamAssassin (comprehensive but heavyweight)
  - [ ] Option 2: rspamd (fast and modern)
  - [ ] Option 3: Simple rule-based (lightweight for alpha)
  - [ ] **Decision:** Implement rule-based for alpha, plan rspamd for production
- [ ] Implement spam filter wrapper (`spam_filter.py`)
  - [ ] `SpamFilter` class
    - [ ] `analyze_email(from_addr, to_addr, subject, body)` method
    - [ ] Return spam score (0-100)
    - [ ] Return detected patterns (list)
  - [ ] Rule-based detection:
    - [ ] Suspicious keywords (examples: common spam terms - load from config file)
    - [ ] Excessive links (>5 links)
    - [ ] Suspicious TLDs (examples: free domains often used for spam - load from config)
    - [ ] All caps subject lines
    - [ ] HTML-only content with no text
    - [ ] Blacklisted sender domains (configurable list)
  - [ ] Scoring system:
    - [ ] Each rule adds points
    - [ ] Threshold: 50+ = spam, 30-49 = suspicious, <30 = clean
  - [ ] Configurable thresholds
  - [ ] Logging (metadata only, no content)
- [ ] Implement rate limiter (`rate_limiter.py`)
  - [ ] `RateLimiter` class
    - [ ] In-memory storage: `{user_id: {action: [(timestamp, count)]}}`
    - [ ] `check_limit(user_id, action, limit, window_seconds)` method
    - [ ] Sliding window algorithm
    - [ ] Automatic cleanup of old entries
  - [ ] Rate limits:
    - [ ] Burner generation: 10 per hour per user
    - [ ] Email sending: 50 per hour per user
    - [ ] Chat messages: 100 per hour per user
    - [ ] Login attempts: 5 per 15 minutes per IP
    - [ ] Signup: 3 per hour per IP
  - [ ] HTTP 429 responses when exceeded
  - [ ] Retry-After header
  - [ ] Exponential backoff calculation
- [ ] Implement abuse detection patterns
  - [ ] Detect repeated identical messages (spam signature)
  - [ ] Detect high-volume burst activity
  - [ ] Detect unusual patterns:
    - [ ] Creating many burners quickly
    - [ ] Sending to many recipients
    - [ ] Large attachment uploads
  - [ ] Flag suspicious users (not auto-ban for alpha)
  - [ ] Log abuse events for manual review
- [ ] Integrate spam checking into email flow
  - [ ] Modify `email_routes.py`:
    - [ ] Add spam check before accepting email
    - [ ] If spam score > 50: reject with 550 SMTP error
    - [ ] If spam score 30-49: accept but mark as [SUSPICIOUS]
    - [ ] If spam score < 30: accept normally
  - [ ] Add spam indicator to email UI
  - [ ] Allow manual "not spam" feedback
- [ ] Integrate rate limiting into all routes
  - [ ] Modify `burner_routes.py`:
    - [ ] Check rate limit before generating burner
    - [ ] Return 429 if exceeded
    - [ ] Show user-friendly error message
  - [ ] Modify `chat_routes.py`:
    - [ ] Check rate limit on message send
    - [ ] Return 429 with retry time
  - [ ] Modify `email_routes.py`:
    - [ ] Check rate limit on send
    - [ ] Show remaining quota to user
  - [ ] Modify auth routes:
    - [ ] Rate limit login attempts
    - [ ] Rate limit signup by IP
- [ ] Implement second domain registrar API
  - [ ] Research Namecheap API
    - [ ] API documentation: https://www.namecheap.com/support/api/
    - [ ] Pricing: check current rates (historically very affordable)
    - [ ] Features: search, purchase, manage DNS
  - [ ] Create `domain_providers/namecheap.py`
    - [ ] `NamecheapAPIClient` class
    - [ ] `search_domains(tld_list, keywords)` method
    - [ ] `purchase_domain(domain, contact_info)` method
    - [ ] `check_availability(domain)` method
    - [ ] Error handling for API failures
    - [ ] Retry logic with exponential backoff
  - [ ] Extend `domain_manager.py`
    - [ ] Support multiple providers in registry
    - [ ] Provider selection strategy:
      - [ ] Round-robin for load balancing
      - [ ] Failover if one provider unavailable
      - [ ] Budget tracking per provider
      - [ ] Prefer cheapest available domain
    - [ ] Multi-provider rotation algorithm
  - [ ] Add environment configuration
    - [ ] `NAMECHEAP_API_KEY`
    - [ ] `NAMECHEAP_API_USER`
    - [ ] `NAMECHEAP_BUDGET_MONTHLY`
    - [ ] `DOMAIN_ROTATION_STRATEGY` (round-robin/cheapest)
- [ ] Add API health checks
  - [ ] `/health/domains` endpoint
  - [ ] Check each registrar API status
  - [ ] Return: available/degraded/down per provider
  - [ ] Show in admin dashboard
  - [ ] Alert if both providers down
- [ ] Write comprehensive tests
  - [ ] `tests/test_spam_filter.py`
    - [ ] Test spam detection rules
    - [ ] Test scoring algorithm
    - [ ] Test threshold boundaries
    - [ ] Test false positive scenarios
  - [ ] `tests/test_rate_limiter.py`
    - [ ] Test rate limit enforcement
    - [ ] Test sliding window
    - [ ] Test concurrent requests
    - [ ] Test limit reset
  - [ ] `tests/test_namecheap_api.py`
    - [ ] Mock API responses
    - [ ] Test domain search
    - [ ] Test domain purchase
    - [ ] Test error handling
  - [ ] `tests/test_domain_rotation.py`
    - [ ] Test multi-provider selection
    - [ ] Test failover logic
    - [ ] Test budget limits

**Files to Create/Modify:**
- `NEW: spam_filter.py` (200-250 lines)
- `NEW: rate_limiter.py` (150-200 lines)
- `NEW: domain_providers/namecheap.py` (250-300 lines)
- `MODIFY: domain_manager.py` - Multi-provider support (100-150 lines added)
- `MODIFY: email_routes.py` - Add spam checking (50-80 lines added)
- `MODIFY: burner_routes.py` - Add rate limiting (30-50 lines added)
- `MODIFY: chat_routes.py` - Add rate limiting (20-30 lines added)
- `NEW: tests/test_spam_filter.py` (150-200 lines)
- `NEW: tests/test_rate_limiter.py` (120-150 lines)
- `NEW: tests/test_namecheap_api.py` (100-120 lines)

**Testing Strategy:**
- Unit tests for all security components
- Integration tests for API calls
- Manual testing: trigger rate limits
- Manual testing: send spam to burner addresses
- Load testing: concurrent users hitting limits

---

### 🟨 Group 4: Legal & Compliance (2-3 days)

**Team Focus:** Policy documents, legal integration, compliance UI, reporting

**Core Tasks:**
- [ ] Finalize policy documents (requires legal counsel review)
  - [ ] Review `ACCEPTABLE_USE_POLICY.md`
    - [ ] Verify prohibited activities list is comprehensive
    - [ ] Confirm law enforcement cooperation language
    - [ ] Update contact information
    - [ ] Set effective date
    - [ ] Add last updated timestamp
  - [ ] Review `TERMS_OF_SERVICE.md`
    - [ ] Verify liability limitations
    - [ ] Confirm dispute resolution process
    - [ ] Update jurisdiction information
    - [ ] Add arbitration clause (if applicable)
    - [ ] Set effective date
  - [ ] Create `PRIVACY_POLICY.md`
    - [ ] What data we collect (very minimal)
      - [ ] Session IDs (temporary)
      - [ ] Usage timestamps (temporary)
      - [ ] No IP addresses (Tor)
      - [ ] No email content (encrypted)
    - [ ] What data we don't collect (most things)
    - [ ] Zero-disk policy explanation
    - [ ] Tor anonymity explanation
    - [ ] Encryption practices (E2E, client-side)
    - [ ] Law enforcement requests policy
    - [ ] User rights (GDPR, CCPA if applicable)
    - [ ] Data retention (automatic deletion)
    - [ ] Cookie usage (session cookies only)
    - [ ] Third-party services (Tor, domain registrars)
    - [ ] Contact for privacy concerns
  - [ ] Get legal counsel review (budget accordingly - costs vary by jurisdiction)
    - [ ] Send drafts for review
    - [ ] Address feedback
    - [ ] Finalize versions
    - [ ] Sign off for production use
- [ ] Create policy display pages
  - [ ] `templates/terms.html`
    - [ ] Render TERMS_OF_SERVICE.md as HTML
    - [ ] Clean, readable typography
    - [ ] Table of contents with anchor links
    - [ ] Print-friendly CSS
    - [ ] "Last updated" timestamp
    - [ ] Contact information footer
  - [ ] `templates/aup.html`
    - [ ] Render ACCEPTABLE_USE_POLICY.md as HTML
    - [ ] Highlight prohibited activities
    - [ ] Contact for abuse reports
    - [ ] Law enforcement cooperation notice
  - [ ] `templates/privacy.html`
    - [ ] Render PRIVACY_POLICY.md as HTML
    - [ ] Clear data collection section
    - [ ] FAQ-style format
    - [ ] Icon indicators (✅ we do / ❌ we don't)
  - [ ] Implement markdown-to-HTML rendering
    - [ ] Use Python-Markdown or similar
    - [ ] Sanitize output (XSS protection)
    - [ ] Cache rendered HTML (in-memory)
- [ ] Add policy routes to `runserver.py`
  - [ ] `/terms` route (public, no auth required)
  - [ ] `/aup` route (public)
  - [ ] `/privacy` route (public)
  - [ ] `/policies` route (shows all three with tabs)
- [ ] Integrate policy acceptance into signup flow
  - [ ] Modify `templates/signup.html`
    - [ ] Add checkboxes:
      - [ ] "I accept the Terms of Service" (required)
      - [ ] "I accept the Acceptable Use Policy" (required)
    - [ ] Add links to open policies in modal or new tab
    - [ ] Disable submit button until checked
    - [ ] Client-side validation
  - [ ] Modify `/signup` route
    - [ ] Verify checkboxes checked (server-side validation)
    - [ ] Store acceptance timestamp in user record
    - [ ] Log acceptance (metadata only, per legal requirement)
    - [ ] Return error if not accepted
- [ ] Add policy links to site footer
  - [ ] Create `templates/footer_partial.html`
  - [ ] Include on all pages:
    - [ ] Terms of Service
    - [ ] Acceptable Use Policy
    - [ ] Privacy Policy
    - [ ] Contact / Report Abuse
    - [ ] Security disclosure
  - [ ] Style footer (subtle, non-intrusive)
- [ ] Add warning banners to appropriate pages
  - [ ] Landing page banner:
    - [ ] ⚠️ "This service cooperates with law enforcement"
    - [ ] ⚠️ "Illegal activity will be reported"
  - [ ] Dashboard banner (dismissible):
    - [ ] "Review our Acceptable Use Policy"
    - [ ] Link to AUP
  - [ ] First-time chat banner:
    - [ ] "Use at your own risk - See Terms of Service"
    - [ ] "This service is for legal use only"
  - [ ] Banner styling (yellow background, clear message)
  - [ ] Dismissible with cookie preference
- [ ] Create abuse reporting mechanism
  - [ ] `templates/report_abuse.html`
    - [ ] Form fields:
      - [ ] Type of abuse (dropdown: spam, harassment, illegal, other)
      - [ ] Description (textarea, 500 char max)
      - [ ] Evidence (optional screenshot/text)
      - [ ] Contact email (optional, for follow-up)
    - [ ] Submit button
    - [ ] CAPTCHA to prevent spam reports
  - [ ] Implement `/report-abuse` route
    - [ ] Validate form input
    - [ ] Rate limit (3 reports per hour per IP)
    - [ ] Store report in memory (24hr retention)
    - [ ] Send email notification to admin
    - [ ] Show confirmation message
    - [ ] Thank user for report
  - [ ] Add "Report Abuse" link in:
    - [ ] Site footer
    - [ ] Email view page (report spam)
    - [ ] Chat page (report user)
- [ ] Store policy acceptance metadata
  - [ ] Extend user record in `user_manager.py`
  - [ ] Fields: `tos_accepted_at`, `aup_accepted_at`
  - [ ] In-memory only (consistent with zero-disk)
  - [ ] Lost on server restart (acceptable for alpha)
  - [ ] Re-prompt on policy updates
- [ ] Create admin view for reports (simple)
  - [ ] `/admin/reports` route (requires admin auth)
  - [ ] List all abuse reports
  - [ ] Show: timestamp, type, description
  - [ ] Action buttons: dismiss, investigate, ban user
  - [ ] For alpha: read-only view sufficient
- [ ] Write tests for policy integration
  - [ ] `tests/test_policy_acceptance.py`
    - [ ] Test signup without accepting policies (should fail)
    - [ ] Test signup with policies accepted (should succeed)
    - [ ] Test policy page rendering
    - [ ] Test abuse report submission
    - [ ] Test rate limiting on reports
    - [ ] Test policy links in footer

**Files to Create/Modify:**
- `NEW: PRIVACY_POLICY.md` (400-500 lines)
- `NEW: templates/terms.html` (100-120 lines)
- `NEW: templates/aup.html` (100-120 lines)
- `NEW: templates/privacy.html` (120-150 lines)
- `NEW: templates/report_abuse.html` (80-100 lines)
- `NEW: templates/footer_partial.html` (30-40 lines)
- `MODIFY: templates/signup.html` - Add policy checkboxes (20-30 lines added)
- `MODIFY: runserver.py` - Add policy and report routes (80-100 lines added)
- `MODIFY: user_manager.py` - Add acceptance tracking (20-30 lines added)
- `NEW: tests/test_policy_acceptance.py` (100-120 lines)
- `NEW: static/policy-modal.css` (50-80 lines)

**Testing Strategy:**
- Manual review of all policy documents
- Legal counsel review (external)
- Manual testing: signup flow with/without acceptance
- Test all policy page renders correctly
- Test abuse report submission
- Test footer displays on all pages

---

## 🔄 Integration Phase (After Parallel Work - 3-4 days)

Once all 4 groups complete their work, these sequential tasks integrate everything:

- [ ] **Cross-Group Integration Testing**
  - [ ] Test complete user journey: signup → key generation → dashboard → chat → email → burner
  - [ ] Verify authentication works with all features
  - [ ] Verify policies are enforced across all features
  - [ ] Verify rate limits apply to authenticated users
  - [ ] Verify spam filter works with authenticated email

- [ ] **End-to-End Testing**
  - [ ] Full signup flow E2E test
  - [ ] Complete chat conversation E2E test
  - [ ] Complete email send/receive E2E test
  - [ ] Burner email generation and use E2E test
  - [ ] Key export and re-import E2E test

- [ ] **Security Audit**
  - [ ] Penetration testing
  - [ ] Memory leak verification
  - [ ] Session isolation testing
  - [ ] Input validation review
  - [ ] XSS/CSRF vulnerability scan
  - [ ] Authentication bypass attempts

- [ ] **Performance Testing**
  - [ ] Load testing (100 concurrent users)
  - [ ] Stress testing (find breaking point)
  - [ ] Memory usage monitoring
  - [ ] Response time measurement
  - [ ] Optimization of slow endpoints

- [ ] **Documentation Updates**
  - [ ] Update README.md with new signup flow
  - [ ] Create user guide with screenshots
  - [ ] Update API documentation
  - [ ] Create troubleshooting guide
  - [ ] Update CHANGELOG for alpha

- [ ] **Bug Fixes**
  - [ ] Address any issues found in testing
  - [ ] Polish rough edges
  - [ ] Improve error messages
  - [ ] Fix any race conditions

---

## 📋 Original Roadmap Sections

The following sections contain the original detailed implementation plans for reference.

## Critical Path Items (Must Complete for Alpha)

### 🔴 Priority 1: User Signup and Authentication Flow (2-3 days)

**Current Status:** Not implemented  
**Target:** Minimal viable signup/login system

#### Technical Design Decisions

**Challenge:** How to implement authentication while maintaining zero-disk policy?

**Options:**
1. **Client-Side Session Keys** (Recommended)
   - Generate session key in browser on signup
   - Store encrypted in browser localStorage
   - Server validates signature, not password
   - Session key rotates periodically
   - No password stored server-side

2. **Ephemeral In-Memory Auth**
   - User accounts stored in memory only
   - Lost on server restart (acceptable for alpha)
   - Simple password hash comparison
   - Session cookies for persistence

3. **Hybrid Approach**
   - Client-side master key
   - Server-side ephemeral session tokens
   - Best of both worlds

**Recommendation:** Start with Option 2 (ephemeral) for alpha, migrate to Option 1 for production.

#### Implementation Tasks

- [ ] Design ephemeral user storage system
  ```python
  class UserManager:
      def __init__(self):
          self.users = {}  # username -> {password_hash, created_at, session_id}
  ```
- [ ] Create signup page template (`templates/signup.html`)
- [ ] Create login page template (`templates/login.html`)
- [ ] Implement `/signup` route
- [ ] Implement `/login` route
- [ ] Implement `/logout` route
- [ ] Add session management decorator
- [ ] Update existing routes to require authentication
- [ ] Add "Remember me" option (browser storage)
- [ ] Create password strength validator
- [ ] Add CSRF protection
- [ ] Write unit tests for auth system
- [ ] Update documentation

**Files to Create/Modify:**
- New: `user_manager.py` - User authentication system
- New: `templates/signup.html` - Signup page
- New: `templates/login.html` - Login page
- Modify: `runserver.py` - Add auth routes and decorators
- New: `tests/test_user_manager.py` - Auth tests

---

### 🔴 Priority 2: Landing Page and Plan Selection (1-2 days)

**Current Status:** Basic landing exists, no plan selection  
**Target:** User dashboard with product selection

#### Implementation Tasks

- [ ] Design new landing page (`templates/landing_new.html`)
  - Welcome message
  - Product overview (Chat, Email, Burner)
  - Plan selection (Free tier for alpha)
  - Sign up / Log in buttons
- [ ] Create user dashboard (`templates/dashboard.html`)
  - Welcome back message
  - Access to Chat
  - Access to Email
  - Access to Burner Emails
  - Settings/Profile
  - Logout
- [ ] Implement `/dashboard` route
- [ ] Create plan selection interface
  - Free tier highlighted
  - Paid tiers grayed out (coming soon)
  - Feature comparison table
- [ ] Update root route to show new landing
- [ ] Add navigation between products
- [ ] Create breadcrumb navigation
- [ ] Responsive design for mobile
- [ ] Write E2E tests for user flow

**Files to Create/Modify:**
- New: `templates/landing_new.html` - New landing page
- New: `templates/dashboard.html` - User dashboard
- New: `templates/plan_selection.html` - Plan selection page
- Modify: `runserver.py` - Add dashboard routes
- New: `static/dashboard.css` - Dashboard styling
- New: `tests/ui-dashboard.spec.js` - Dashboard tests

---

### 🔴 Priority 3: Key Management UI and Education (2-3 days)

**Current Status:** PGP support exists, no UI for key management  
**Target:** User-friendly key generation and management interface

#### Implementation Tasks

**Key Generation Wizard:**
- [ ] Create key generation modal (`templates/key_wizard.html`)
- [ ] Add "Generate New Key" button
- [ ] Add "Import Existing Key" option
- [ ] Real-time key generation in browser
- [ ] Display generated public key
- [ ] Show key fingerprint
- [ ] Download private key button (secure export)
- [ ] Educational tooltips:
  - "Generated in your browser only"
  - "We never see your private key"
  - "Save this key - we cannot recover it"
  - "Use this key to encrypt messages"

**Key Management Interface:**
- [ ] Create key management page (`templates/key_management.html`)
- [ ] Show current key status (has key / no key)
- [ ] Display public key (read-only)
- [ ] Display key fingerprint
- [ ] Export private key button
- [ ] Import key interface
- [ ] Delete key confirmation
- [ ] Key backup reminder
- [ ] Last backup timestamp

**User Education:**
- [ ] First-time user modal
- [ ] Onboarding walkthrough
- [ ] "How it works" explainer:
  - Client-side encryption
  - Key management basics
  - Privacy guarantees
  - Limitations of anonymity
- [ ] Tooltip system
- [ ] Help documentation links
- [ ] FAQ section

**JavaScript Enhancements:**
- [ ] Enhance `static/pgp-manager.js`:
  - Key generation UI integration
  - Key export functionality
  - Key import validation
  - Key strength indicator
  - Backup reminder system
- [ ] Add key management event handlers
- [ ] Add educational modal system
- [ ] Add progress indicators

**Files to Create/Modify:**
- New: `templates/key_wizard.html` - Key generation wizard
- New: `templates/key_management.html` - Key management page
- New: `templates/onboarding.html` - First-time user onboarding
- Modify: `static/pgp-manager.js` - Add UI integration
- New: `static/key-management.css` - Styling
- Modify: `runserver.py` - Add key management routes
- New: `tests/test_key_management.spec.js` - Key UI tests

---

### 🔴 Priority 4: Spam Filtering System (2-3 days)

**Current Status:** No spam filtering  
**Target:** Basic spam detection and rate limiting

#### Implementation Tasks

**Spam Filter Integration:**
- [ ] Research spam filter options:
  - SpamAssassin (comprehensive, heavyweight)
  - rspamd (fast, modern)
  - Simple rule-based (lightweight for alpha)
- [ ] Implement spam filter wrapper class
- [ ] Add spam scoring system
- [ ] Configure spam threshold
- [ ] Add spam filter to email receive flow
- [ ] Add spam quarantine (optional)
- [ ] Log spam detections (metadata only)

**Rate Limiting:**
- [ ] Implement rate limiter class
  ```python
  class RateLimiter:
      def __init__(self):
          self.actions = {}  # user_id -> [(action, timestamp)]
      
      def check_limit(self, user_id, action, limit, window):
          # Return True if under limit, False if exceeded
  ```
- [ ] Add rate limits:
  - Burner email generation: 10 per hour
  - Email sending: 50 per hour
  - Chat messages: 100 per hour
- [ ] Add rate limit HTTP responses (429 Too Many Requests)
- [ ] Add rate limit UI feedback
- [ ] Implement exponential backoff

**Abuse Detection:**
- [ ] Add suspicious pattern detection
- [ ] Flag high-volume users
- [ ] Detect repeated content (spam signatures)
- [ ] Add temporary auto-ban for severe abuse
- [ ] Log abuse events (for admin review)

**Files to Create/Modify:**
- New: `spam_filter.py` - Spam filtering system
- New: `rate_limiter.py` - Rate limiting system
- Modify: `email_routes.py` - Add spam checking
- Modify: `burner_routes.py` - Add rate limiting
- Modify: `chat_routes.py` - Add rate limiting
- New: `tests/test_spam_filter.py` - Spam filter tests
- New: `tests/test_rate_limiter.py` - Rate limiter tests

---

### 🔴 Priority 5: Second Domain Registrar API (1-2 days)

**Current Status:** Only Porkbun API implemented  
**Target:** At least 2 domain registrar APIs

#### Options for Second API

1. **Namecheap API**
   - Well-documented
   - Affordable domains
   - Good Python libraries

2. **GoDaddy API**
   - Large provider
   - Comprehensive API
   - Higher prices

3. **NameSilo API**
   - Privacy-focused
   - Low prices
   - Simple API

**Recommendation:** Namecheap for balance of price, features, and documentation.

#### Implementation Tasks

- [ ] Research Namecheap API
- [ ] Create API wrapper class
  ```python
  class NamecheapAPIClient:
      def search_domains(self, tld_list, budget_limit):
          pass
      
      def purchase_domain(self, domain):
          pass
  ```
- [ ] Extend `domain_manager.py` to support multiple APIs
- [ ] Implement domain rotation strategy:
  - Round-robin between registrars
  - Fallback if one fails
  - Budget tracking per registrar
- [ ] Add API configuration to environment
- [ ] Update domain rotation endpoint
- [ ] Add API health checks
- [ ] Write unit tests
- [ ] Update documentation

**Files to Create/Modify:**
- New: `domain_providers/namecheap.py` - Namecheap API client
- Modify: `domain_manager.py` - Multi-provider support
- Modify: `email_routes.py` - Use multi-provider rotation
- New: `tests/test_namecheap_api.py` - Namecheap tests
- Modify: `DOMAIN_REGISTRAR_API.md` - Document second API

---

### 🔴 Priority 6: Policy Documents Integration (1 day)

**Current Status:** Draft policies created, not integrated  
**Target:** Policies displayed and acknowledged by users

#### Implementation Tasks

- [ ] Review and finalize policy documents:
  - [ ] Legal counsel review (if possible)
  - [ ] Update contact information
  - [ ] Set effective dates
- [ ] Create policy display pages:
  - [ ] `/terms` route → TERMS_OF_SERVICE.md
  - [ ] `/aup` route → ACCEPTABLE_USE_POLICY.md
  - [ ] `/privacy` route → PRIVACY_POLICY.md (needs creation)
- [ ] Add policy acceptance to signup flow:
  - [ ] Checkbox "I accept the Terms of Service"
  - [ ] Checkbox "I accept the Acceptable Use Policy"
  - [ ] Links to read full policies
  - [ ] Cannot proceed without acceptance
- [ ] Add policy links to footer:
  - [ ] Terms of Service
  - [ ] Acceptable Use Policy
  - [ ] Privacy Policy
  - [ ] Contact / Report Abuse
- [ ] Add warning banners:
  - [ ] "This service cooperates with law enforcement"
  - [ ] "Illegal activity will be reported"
  - [ ] "Use at your own risk"
- [ ] Store acceptance timestamp (in-memory)

**Files to Create/Modify:**
- New: `templates/terms.html` - Terms display
- New: `templates/aup.html` - AUP display
- New: `templates/privacy.html` - Privacy policy display
- Modify: `templates/signup.html` - Add acceptance checkboxes
- Modify: `runserver.py` - Add policy routes
- New: `tests/test_policy_acceptance.py` - Policy tests

---

## Secondary Priority Items (Important but Not Blocking)

### 🟡 Priority 7: Attachment System (2-3 days)

**Status:** Not implemented  
**Required for:** Complete email functionality

#### Implementation Tasks

- [ ] Design file upload system
- [ ] Implement file upload endpoint
- [ ] Add file type validation (text-based only)
- [ ] Add file size limits (e.g., 10MB max)
- [ ] Store attachments in memory
- [ ] Add attachment to email data structure
- [ ] Create download attachment endpoint
- [ ] Add virus scanning (optional but recommended)
- [ ] Update email templates to show attachments
- [ ] Add attachment UI in compose page
- [ ] Write tests

**Allowed File Types (for alpha):**
- .txt - Plain text
- .md - Markdown
- .pdf - PDF documents
- .doc/.docx - Word documents
- .csv - CSV files
- .json - JSON files
- .xml - XML files

**Prohibited:**
- Images (.jpg, .png, .gif, etc.)
- Videos (.mp4, .avi, .mov, etc.)
- Executables (.exe, .sh, .bat, etc.)
- Archives (.zip, .tar, .rar, etc.) - can contain executables

---

### 🟡 Priority 8: Privacy Policy (1 day)

**Status:** Not created  
**Required for:** Legal compliance

#### Implementation Tasks

- [ ] Draft privacy policy document
- [ ] Legal counsel review
- [ ] Cover topics:
  - What data we collect (very little)
  - What data we don't collect (most things)
  - Zero-disk policy
  - Tor anonymity
  - Encryption practices
  - Law enforcement requests
  - User rights
  - Data retention (automatic deletion)
  - Cookie usage
  - Third-party services (Tor, domain registrars)
- [ ] Add to repository as `PRIVACY_POLICY.md`
- [ ] Integrate into UI

---

### 🟡 Priority 9: Comprehensive Testing (3-5 days)

**Status:** Good test coverage exists, need more  
**Required for:** Alpha quality assurance

#### Implementation Tasks

**Unit Tests:**
- [ ] Test user authentication
- [ ] Test key management
- [ ] Test spam filtering
- [ ] Test rate limiting
- [ ] Test policy acceptance
- [ ] Test attachment handling

**Integration Tests:**
- [ ] Test complete signup flow
- [ ] Test chat with encryption
- [ ] Test email with encryption
- [ ] Test burner email lifecycle
- [ ] Test domain rotation
- [ ] Test spam detection

**E2E Tests (Playwright):**
- [ ] Test user registration
- [ ] Test login/logout
- [ ] Test key generation
- [ ] Test key import/export
- [ ] Test sending encrypted message
- [ ] Test receiving encrypted message
- [ ] Test burner email creation
- [ ] Test policy acceptance

**Security Tests:**
- [ ] Memory leak verification
- [ ] PGP encryption validation
- [ ] Session isolation testing
- [ ] Input validation testing
- [ ] XSS/CSRF testing
- [ ] Rate limit testing
- [ ] Authentication bypass attempts

**Manual Testing:**
- [ ] Complete user flow in Tor Browser
- [ ] Test on different browsers
- [ ] Test mobile responsiveness
- [ ] Test with screen readers
- [ ] Test with JavaScript disabled
- [ ] Stress testing (multiple users)

---

### 🟡 Priority 10: Documentation Updates (1-2 days)

**Status:** Good docs exist, need updates  
**Required for:** User and developer guidance

#### Implementation Tasks

- [ ] Update README.md:
  - [ ] Alpha release status
  - [ ] New signup flow
  - [ ] Key management instructions
  - [ ] Updated screenshots
- [ ] Create user guide:
  - [ ] Getting started
  - [ ] How to sign up
  - [ ] How to generate keys
  - [ ] How to use chat
  - [ ] How to use email
  - [ ] How to use burner emails
  - [ ] Security best practices
- [ ] Create FAQ document
- [ ] Update API documentation
- [ ] Create troubleshooting guide
- [ ] Add deployment guide updates
- [ ] Create CHANGELOG for alpha

---

## Nice to Have (Post-Alpha)

### 🟢 Priority 11: UI/UX Polish

- [ ] Consistent styling across all pages
- [ ] Dark mode option
- [ ] Mobile-responsive design
- [ ] Accessibility improvements
- [ ] Loading indicators
- [ ] Better error messages
- [ ] Tooltips and help text
- [ ] Keyboard shortcuts

### 🟢 Priority 12: Advanced Features

- [ ] Multi-device key sync (challenging with zero-disk!)
- [ ] Contact management
- [ ] Email folders/labels
- [ ] Search functionality
- [ ] Export/backup tools
- [ ] Admin dashboard
- [ ] Usage statistics (privacy-preserving)
- [ ] Notification system

---

## Critical Decision Points

### Decision 1: Privacy vs Law Enforcement Cooperation 🔴

**Issue:** Requirements contradict each other:
- Zero-disk policy + ephemeral services = no data to provide
- Law enforcement cooperation = need data to provide

**Options:**

**A. Limited Metadata Logging**
- Pros: Can assist investigations, comply with legal requests
- Cons: Reduces privacy, adds complexity, conflicts with zero-disk
- Implementation: Separate encrypted logging system, 30-day retention

**B. Policy as Deterrent Only**
- Pros: Maintains zero-disk policy, simple
- Cons: Cannot actually assist LE, policy is somewhat hollow
- Implementation: Strong warning language, but no actual enforcement capability

**C. Hybrid Approach**
- Pros: Balance between extremes
- Cons: Complex, may not satisfy either goal
- Implementation: Normal operation is zero-disk, emergency logging capability

**Recommendation:** Discuss with legal counsel and stakeholders. For alpha, implement Option B (policy as deterrent) and clearly document limitations. Can add logging post-alpha if required.

**Action Items:**
- [ ] Schedule decision meeting
- [ ] Document decision rationale
- [ ] Update policies to reflect decision
- [ ] Implement chosen approach
- [ ] Update documentation

---

### Decision 2: Authentication Persistence

**Issue:** How to maintain user sessions across server restarts?

**Options:**

**A. Ephemeral Only (Recommended for Alpha)**
- Users must sign up again after server restart
- Fully consistent with zero-disk policy
- Simple implementation
- Acceptable for alpha testing

**B. Client-Side Persistence**
- Store session key in browser
- Re-authenticate automatically
- Still zero-disk on server
- Better UX

**C. Encrypted Disk Storage**
- Store user accounts encrypted on disk
- Compromises zero-disk policy
- Best UX
- Requires key management complexity

**Recommendation:** Start with A for alpha, migrate to B for production.

---

## Timeline Estimate

### Week 1: Core User System
- Days 1-2: User signup and authentication
- Days 3-4: Landing page and dashboard
- Day 5: Policy integration

### Week 2: Key Management and Security
- Days 1-3: Key management UI and education
- Days 4-5: Spam filtering and rate limiting

### Week 3: Domain APIs and Attachments
- Days 1-2: Second registrar API
- Days 3-5: Attachment system (if time permits)

### Week 4: Testing and Polish
- Days 1-3: Comprehensive testing
- Days 4-5: Documentation and bug fixes

**Total:** 4 weeks for critical path + secondary items

---

## Definition of Done (Alpha Release)

### Must Have (Blockers) ✅
- [ ] User signup and authentication flow
- [ ] Plan selection (free tier)
- [ ] Key management UI with education
- [ ] Policy documents displayed and accepted
- [ ] Spam filtering on burner emails
- [ ] Second domain registrar API
- [ ] Rate limiting implemented
- [ ] All existing tests passing
- [ ] Basic E2E tests for new features
- [ ] Security review complete
- [ ] Documentation updated

### Should Have (Important) ⚠️
- [ ] Attachment system (can defer)
- [ ] Privacy policy
- [ ] Comprehensive test suite
- [ ] Performance testing
- [ ] Mobile responsiveness

### Nice to Have (Post-Alpha) 🟢
- [ ] UI polish
- [ ] Advanced features
- [ ] Internationalization
- [ ] Admin dashboard

---

## Risk Mitigation

### Technical Risks

**Risk:** Authentication breaks zero-disk policy  
**Mitigation:** Use ephemeral in-memory storage for alpha, clearly document that accounts are lost on restart

**Risk:** Spam filter too aggressive  
**Mitigation:** Configurable thresholds, manual review capability, user feedback

**Risk:** Key generation too complex for users  
**Mitigation:** Extensive tooltips, video tutorial, pre-alpha user testing

**Risk:** Second API integration difficult  
**Mitigation:** Start with simple registrar (Namecheap), abstract API interface, thorough testing

### Legal Risks

**Risk:** Policy language not legally sound  
**Mitigation:** Legal counsel review, standard boilerplate, clear disclaimers

**Risk:** Cannot fulfill law enforcement requests  
**Mitigation:** Clearly document limitations, manage expectations, consider limited logging

**Risk:** Liability for user actions  
**Mitigation:** Strong AUP, clear disclaimers, good-faith efforts to prevent abuse

### Schedule Risks

**Risk:** 4 weeks too optimistic  
**Mitigation:** Prioritized critical path, can defer nice-to-haves, regular progress reviews

**Risk:** Testing takes longer than expected  
**Mitigation:** Start testing early, automated tests, continuous integration

---

## Success Metrics

### Alpha Success Criteria

**Functionality:**
- [ ] Users can sign up and log in
- [ ] Users can generate/import keys
- [ ] Users can send encrypted messages
- [ ] Burner emails work with spam filtering
- [ ] Domain rotation works with 2+ APIs
- [ ] No critical security vulnerabilities

**Usability:**
- [ ] New users can complete signup in < 5 minutes
- [ ] Key generation is understandable
- [ ] Navigation is intuitive
- [ ] Works in Tor Browser

**Performance:**
- [ ] Page load < 3 seconds
- [ ] Message send < 1 second
- [ ] Burner generation < 2 seconds
- [ ] Handles 100 concurrent users

**Security:**
- [ ] All tests passing
- [ ] No high/critical vulnerabilities
- [ ] Encryption working correctly
- [ ] Memory cleared after use

---

## Next Steps

1. **Review this roadmap** with team/stakeholders
2. **Make critical decisions** (privacy vs cooperation, auth persistence)
3. **Set alpha release date** based on timeline
4. **Assign tasks** to developers
5. **Set up project tracking** (GitHub issues, project board)
6. **Begin implementation** starting with Priority 1
7. **Regular standup/reviews** to track progress
8. **User testing** as features complete
9. **Security review** before release
10. **Alpha launch!** 🚀

---

**Document Status:** Draft - Ready for Review  
**Last Updated:** January 6, 2026  
**Author:** AI Assistant based on ALPHA_READINESS_ASSESSMENT.md
