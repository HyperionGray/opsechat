# Alpha Release Implementation Roadmap

**Created:** January 6, 2026  
**Target Alpha Release:** [TBD]  
**Current Status:** ~73% Complete  
**Estimated Time to Alpha:** 3-4 weeks with focused effort

---

## Overview

This document provides a detailed implementation roadmap for bringing opsechat to alpha release, based on the comprehensive assessment in ALPHA_READINESS_ASSESSMENT.md.

---

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
