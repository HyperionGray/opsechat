# START HERE - OpSecChat Developer Guide

## What is This Repo?

**OpSecChat** (formerly DropChat) is a secure, ephemeral, anonymous chat and email system that runs over the Tor network as a hidden service. It's designed for privacy-conscious communication where operational security (OPSEC) is paramount.

At its core, OpSecChat creates disposable mini-chat servers that can be spun up instantly with a single command. The host generates a Tor hidden service (.onion address), shares it with participants, and everyone can chat anonymously through Tor Browser - no registration, no accounts, no data stored on disk. When you're done, kill the server and everything disappears.

Beyond chat, OpSecChat has evolved into a comprehensive privacy toolkit including:
- **Ephemeral Chat**: Temporary chat rooms with randomized usernames and auto-expiring messages (3 minutes)
- **Burner Email System**: Guerrillamail-style rotating anonymous email addresses with real SMTP/IMAP support
- **Email Security Tools**: Spoofing detection, phishing simulation, and security research features
- **PGP Encryption**: Optional end-to-end encryption for both chat and email
- **Domain Rotation**: Automated cheap domain purchasing (.xyz, .club) via Porkbun API

## Why Is This Useful?

**The Problem**: Traditional communication tools leak metadata, require accounts, store conversation history, and can be subpoenaed or hacked. Even "secure" messaging apps often compromise on anonymity or leave traces.

**The Solution**: OpSecChat provides truly ephemeral, anonymous communication:
- **No Persistent Identity**: No accounts, usernames are randomized per session
- **Memory-Only Storage**: Nothing touches disk except the application code itself
- **Tor Hidden Service**: Runs as a .onion site, ensuring both server and clients are anonymous
- **Disposable by Design**: Each server instance is unique and temporary
- **Defense in Depth**: Multiple security layers (Tor, PGP, sanitization, auto-expiry)

**Use Cases**:
- Anonymous coordination among activists or journalists
- Secure communication for security researchers
- Whistleblower contact channels
- Privacy-focused team collaboration
- Security awareness training (phishing simulations)
- Penetration testing and social engineering research (authorized only)

## Who Is It For?

**Primary Audience**:
- **Privacy Advocates**: People who need anonymous, secure communication
- **Security Researchers**: Professionals conducting authorized security testing
- **Journalists & Activists**: Those working in high-risk environments
- **Developers**: Anyone interested in privacy-preserving architecture

**Developer Profile**:
If you're reading this, you're likely a developer interested in:
- Tor hidden service implementation
- Flask web application architecture
- Privacy-preserving system design
- Security tooling and testing frameworks
- Docker/container deployment
- CI/CD automation

You don't need to know Python specifically, but you should understand web applications, HTTP, sessions, and basic security concepts.

## Repository Deep Dive

### Architecture Overview

OpSecChat is a **Flask-based web application** that creates ephemeral Tor hidden services using the `stem` library (Tor control protocol). The architecture is deliberately simple and monolithic to minimize attack surface and complexity.

**Core Technologies**:
- **Python 3.8+**: Primary language
- **Flask 3.0+**: Web framework (no database, pure in-memory)
- **stem 1.8.2+**: Tor control library for creating hidden services
- **Tor**: Network anonymity layer
- **Docker/Podman**: Containerization for deployment

**Key Architectural Decisions**:

1. **In-Memory Everything**: No database, no disk writes (except application code). All chat messages, emails, sessions stored in Python dictionaries/lists. This ensures true ephemerality - when the process dies, everything is gone.

2. **Ephemeral Hidden Services**: Each server start creates a new .onion address via Tor's ephemeral hidden service feature. No configuration files, no persistent keys. When you stop the server, the hidden service vanishes.

3. **Session-Based Identity**: Uses Flask sessions with random session keys. User IDs are generated randomly on first visit (see `id_generator()` in `runserver.py:38-52`).

4. **Auto-Expiring Messages**: Background cleanup runs on every request, deleting messages older than 180 seconds (see `check_older_than()` at `runserver.py:56-64` and cleanup logic at `runserver.py:290-301`).

5. **Blueprint Pattern (Partial)**: The codebase is transitioning from a monolithic `runserver.py` to Flask Blueprints. Currently:
   - Old monolithic: `runserver.py` (legacy, still works)
   - New modular: `app_factory.py` + blueprints (`chat_routes.py`, `email_routes.py`, `burner_routes.py`, `security_routes.py`)

### Code Structure

```
opsechat/
├── runserver.py              # Main entry point (legacy monolithic app)
├── app_factory.py            # Flask app factory (newer blueprint-based)
├── chat_routes.py            # Chat functionality (blueprint)
├── email_routes.py           # Email inbox/compose (blueprint)
├── burner_routes.py          # Burner email system (blueprint)
├── security_routes.py        # Security testing tools (blueprint)
├── review_routes.py          # User review system
├── email_system.py           # Email storage and PGP handling
├── email_transport.py        # SMTP/IMAP client wrapper
├── email_security_tools.py   # Spoofing/phishing detection
├── domain_manager.py         # Porkbun API for domain rotation
├── utils.py                  # Shared utilities (id_generator, etc.)
├── state_manager.py          # State persistence (experimental)
├── monitoring.py             # Performance monitoring hooks
├── templates/                # Jinja2 HTML templates
│   ├── drop.html            # Main chat interface
│   ├── email_*.html         # Email system templates
│   └── landing*.html        # Landing/detection pages
├── static/                   # CSS, JS, images
│   ├── jquery.js            # jQuery 3.7.1 (bundled, XSS-patched)
│   └── drop.css             # Minimal styling
├── tests/                    # Playwright E2E tests
│   ├── basic.spec.js        # Structure/import tests
│   ├── e2e.spec.js          # Full flow tests
│   └── mock_server.py       # Test fixture server
├── aws/                      # AWS deployment templates
│   └── cloudformation/      # ECS Fargate infrastructure
├── quadlets/                 # Podman Quadlet systemd units
├── docker-compose.yml        # Docker Compose setup
├── Dockerfile               # Container image definition
├── requirements.txt         # Python dependencies
├── package.json             # Node.js test dependencies
└── setup.py                 # Python package metadata
```

### How It Works Technically

#### 1. Server Startup (`runserver.py:850-906`)

```python
# Connect to Tor control port (default 127.0.0.1:9051)
controller = Controller.from_port(address=tor_host, port=tor_port)
controller.authenticate()

# Create ephemeral hidden service
# Maps external port 80 to local Flask port 5000
result = controller.create_ephemeral_hidden_service({80: 5000}, await_publication=True)

# Get the .onion address
hostname = result.service_id  # e.g., "abc123...xyz.onion"
path = id_generator(size=32)  # Random 32-char path for obscurity
full_url = f"{hostname}.onion/{path}"

# Start Flask server
app.run(host='0.0.0.0', debug=False, threaded=True)
```

**What's Happening**:
- Tor must already be running with ControlPort enabled (9051)
- `stem` talks to Tor control port to create a hidden service dynamically
- Tor publishes the service to the network (takes 30-90 seconds)
- Flask binds to 0.0.0.0:5000 (accessible to Tor, not directly to internet)
- Users connect via Tor Browser → Tor network → hidden service → Flask

#### 2. Chat Flow (JavaScript Disabled)

**Route**: `/<path>/noscript` → `runserver.py:265-281`

```python
@app.route('/<string:url_addition>/noscript', methods=["GET"])
def drop_noscript(url_addition):
    # Verify URL path matches (prevents enumeration)
    if url_addition != app.config["path"]:
        return ('', 404)
    
    # Create session if first visit
    if "_id" not in session:
        session["_id"] = id_generator()  # Random user ID
        chatters.append(session["_id"])
        session["color"] = get_random_color()  # RGB tuple for display
    
    return render_template("drop.html", script_enabled=False, ...)
```

**Message Submission**: `/<path>/chats` (POST) → `runserver.py:283-325`
- Receives form POST with `dropdata` field
- Sanitizes message: `re.sub(r'([^\s\w\.\?\!\:\)\(\*]|_)+', '', msg)`
  - **Exception**: PGP messages (detected via `-----BEGIN PGP MESSAGE-----`) are NOT sanitized
- Adds timestamp, user ID, color to message dict
- Appends to global `chatlines` list (in-memory)
- Keeps only last 13 messages: `chatlines = chatlines[-13:]`
- Auto-cleanup: Deletes messages older than 180 seconds

#### 3. Chat Flow (JavaScript Enabled)

**Route**: `/<path>/yesscript` → `runserver.py:246-262`

Same as noscript, but template renders with JavaScript. JavaScript polls `/<path>/chatsjs` every 2 seconds for updates.

**AJAX Endpoint**: `/<path>/chatsjs` → `runserver.py:328-368`
- Returns JSON array of chat messages
- Same cleanup logic as noscript
- JavaScript updates DOM without page reload

#### 4. Email System

**Storage**: `email_system.py:15-40` - `EmailStorage` class
- In-memory dict: `{user_id: [email_list]}`
- No encryption at rest (it's in RAM, cleared on exit)
- PGP support for message content encryption

**Burner Email Generation**: `email_system.py:210-250` - `BurnerEmailManager`
```python
def generate_burner_email(self, user_id, lifetime_seconds=3600):
    # Generate random email: random123@domain.com
    local_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = self.default_domain  # "opsechat.onion" or custom
    email = f"{local_part}@{domain}"
    
    # Store with expiry timestamp
    self.burners[email] = {
        'user_id': user_id,
        'created': datetime.now(),
        'expires': datetime.now() + timedelta(seconds=lifetime_seconds)
    }
    return email
```

**SMTP/IMAP Support**: `email_transport.py:10-150` - `EmailTransportManager`
- Wraps Python `smtplib` and `imaplib`
- Credentials stored in-memory only (not persisted)
- Can send real emails via configured SMTP server
- Can fetch emails from IMAP server

#### 5. Domain Rotation (`domain_manager.py`)

Integrates with Porkbun API to automatically purchase cheap domains (.xyz, .club, etc.) for email rotation:

```python
class PorkbunAPIClient:
    def search_domains(self, budget=10.0):
        # Search for available domains under budget
        # Porkbun API: GET /pricing/get
        
    def purchase_domain(self, domain):
        # Buy domain via API
        # Porkbun API: POST /domain/create
```

Budget tracking prevents runaway costs. Monthly limit is configurable.

#### 6. Security Features

**Message Sanitization**: `runserver.py:311, 355`
- Regex removes most special characters
- Prevents XSS injection in chat messages
- **Critical**: PGP messages bypass sanitization (needed for encryption)

**Header Removal**: `runserver.py:179-183`
- Strips `Server` and `Date` headers to prevent fingerprinting
- Makes it harder to identify Flask/Python version

**jQuery XSS Fix**: jQuery 3.7.1 bundled in `static/jquery.js`
- Patched CVE-2020-11023 and CVE-2020-11022
- See `SECURITY.md` and `JQUERY_SECURITY_UPDATE.md`

**Session Keys**: `runserver.py:54`
```python
app.secret_key = id_generator(size=64)
```
- **Note**: Uses `random` module, not `secrets`. This is acceptable because:
  - Sessions are ephemeral (cleared on restart)
  - No persistent authentication tokens
  - Tor hidden service already provides network-level anonymity
- **If you add persistent auth**: Switch to `secrets.token_hex(32)`

**Spoofing Detection**: `email_security_tools.py:10-120` - `SpoofingTester`
- Detects unicode lookalikes (e.g., "раypal.com" using Cyrillic)
- Checks for typosquatting (e.g., "paypa1.com")
- Homograph attack detection

**Phishing Simulator**: `email_security_tools.py:125-300` - `PhishingSimulator`
- Generates realistic phishing emails for training
- Tracks user responses (click tracking)
- Gamified scoring system

### Deployment Options

The project supports multiple deployment strategies:

**1. Docker Compose (Recommended for Development)**
```bash
./compose-up.sh
```
- Spins up two containers: Tor daemon + OpSecChat app
- Fully isolated network
- Easy teardown: `./compose-down.sh`
- See `docker-compose.yml` and `Dockerfile`

**2. Podman Quadlets (Recommended for Production)**
```bash
podman build -t localhost/opsechat:latest .
./install-quadlets.sh
systemctl --user start opsechat-app
```
- Systemd integration for auto-restart
- Rootless containers
- Native service management
- See `quadlets/` directory and `QUADLETS.md`

**3. AWS ECS Fargate (Enterprise Production)**
```bash
aws cloudformation create-stack \
  --stack-name opsechat-infrastructure-production \
  --template-body file://aws/cloudformation/opsechat-infrastructure.yml
```
- Full infrastructure as code
- VPC isolation, secrets management, monitoring
- See `aws/` directory and `AWS_DEPLOYMENT.md`

**4. Native Installation (Deprecated)**
```bash
ALLOW_DEPRECATED_INSTALL=1 ./install.sh
```
- Direct Python installation
- No longer maintained (use containers instead)

### Testing Infrastructure

**Playwright E2E Tests**: `tests/*.spec.js`
- Multi-browser testing (Chromium, Firefox, WebKit)
- Headless and headed modes
- Mock server fixture: `tests/mock_server.py`

**Run Tests**:
```bash
npm install              # Install Playwright
npx playwright install   # Install browsers
npm test                 # Run all tests
npm run test:headless    # Headless only
npm run test:headed      # Visible browser (debugging)
```

**Test Coverage**:
- Basic structure validation (`basic.spec.js`)
- Full user flows (`e2e.spec.js`)
- UI behavior (script/noscript modes)
- Security headers validation
- Session handling

**CI/CD**: `.github/workflows/`
- Amazon Q code review integration
- Automated security scanning (Bandit, Safety, Semgrep, CodeQL)
- Multi-platform testing
- See `CICD_REVIEW_SUMMARY.md`

### Unique/Interesting Code Patterns

**1. Reverse Index Deletion for Cleanup**

**Bug**: Original code deleted from list while iterating forward, causing index shifts and missed deletions.

**Fix**: Collect indices, delete in reverse order (`runserver.py:300-301`):
```python
for _del in reversed(to_delete):
    chatlines.pop(_del)
```

This ensures indices remain valid as we delete.

**2. PGP Message Detection**

PGP-encrypted messages are special-cased throughout the codebase to prevent wrapping/sanitization:
```python
is_pgp = "-----BEGIN PGP MESSAGE-----" in chat_dic["msg"]
if is_pgp:
    chats = [chat_dic]  # Don't wrap long PGP blocks
else:
    # Normal text wrapping
    for message in textwrap.wrap(chat_dic["msg"], width=69):
        ...
```

**3. Dual JavaScript/No-JavaScript Support**

Every feature has two routes:
- `/<path>/feature` - Base route (often auto-detects JS)
- `/<path>/feature/yesscript` - JavaScript version
- `/<path>/feature/noscript` - No JavaScript version

This ensures Tor Browser users with "Safest" settings (JS disabled) can still use the app.

**4. Session-Based User Identification**

No registration, no usernames. On first visit:
```python
if "_id" not in session:
    session["_id"] = id_generator()  # Random 6-char string
    session["color"] = get_random_color()  # RGB tuple
```

The session cookie (encrypted by Flask) identifies the user. When the browser closes or session expires, identity is lost (by design).

**5. Global State Management**

Uses module-level globals for simplicity:
```python
chatters = []         # List of active user IDs
chatlines = []        # List of chat message dicts
reviews = []          # List of review dicts
```

**Trade-off**: Simple but not thread-safe without Flask's GIL. Works for ephemeral use but wouldn't scale horizontally. For multi-process deployment, you'd need Redis or similar.

### Security Considerations

**What's Protected**:
- Network anonymity (Tor hidden service)
- Message ephemerality (auto-deletion, no disk writes)
- User anonymity (no accounts, random IDs)
- XSS prevention (sanitization + jQuery patch)
- Fingerprinting mitigation (header removal)

**What's NOT Protected** (by design or limitation):
- Timing attacks (message timestamps could correlate users)
- Active attackers controlling the server (it's self-hosted, you trust yourself)
- Compromised client machines (Tor Browser security is user's responsibility)
- Long-term key management (ephemeral keys mean no forward secrecy for PGP)

**Known Limitations**:
- `random` instead of `secrets` for session keys (acceptable for ephemeral use)
- No rate limiting (could be DoS'd by spamming messages)
- No CAPTCHA (Tor exit nodes could be blocked elsewhere, but hidden services are fine)
- Single-server (no horizontal scaling without refactoring global state)

## How to Build On This

### Getting Started as a Developer

**1. Set Up Local Environment**
```bash
# Clone the repo
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat

# Install Python dependencies
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install Tor (if not already installed)
# Ubuntu/Debian: sudo apt install tor
# macOS: brew install tor
# Windows: Download Tor Browser or Tor Expert Bundle

# Start Tor with control port
tor --ControlPort 9051 --CookieAuthentication 0

# In another terminal, run the app
python runserver.py

# You'll see something like:
# [*] Your service is available at: abc123...xyz.onion/random32charpath
```

**2. Explore the Codebase**

Start with these files in order:
1. `README.md` - High-level overview and features
2. `runserver.py` - Main application logic (start here for understanding flow)
3. `templates/drop.html` - Chat UI (see how noscript/script modes work)
4. `email_system.py` - Email storage and burner management
5. `tests/e2e.spec.js` - See how features are tested end-to-end

**3. Run Tests**
```bash
npm install
npx playwright install
npm test
```

**4. Make a Small Change**

Try adding a new chat command or email feature. Good first tasks are listed below.

### Improvement Tasks (Easy → Moderate → Difficult)

#### EASY (Good First Issues)

**1. Add Message Count Display**
- **What**: Show "Messages: 5/13" in the chat interface
- **Where**: Modify `templates/drop.html`, add to template variables in `runserver.py:326`
- **Why**: Helps users understand message limit
- **Difficulty**: Just template changes, no logic

**2. Add Copy-to-Clipboard for .onion URL**
- **What**: Button to copy the full service URL
- **Where**: `templates/landing.html`, add JavaScript
- **Why**: Easier URL sharing
- **Difficulty**: Basic JS, already have jQuery

**3. Configurable Message Retention Time**
- **What**: Environment variable for message expiry (default 180s)
- **Where**: `runserver.py:56` - change default parameter `secs_to_live = 180` to `secs_to_live = int(os.environ.get('MESSAGE_EXPIRY', 180))`
- **Why**: Some users might want longer/shorter retention
- **Difficulty**: Simple env var usage

**4. Add Markdown Support for Chat Messages**
- **What**: Render `**bold**`, `*italic*`, `` `code` `` in chat
- **Where**: `templates/drop.html`, add markdown JS library or Python `markdown` module
- **Why**: Richer formatting for technical discussions
- **Difficulty**: Library integration, sanitization concerns (be careful!)

**5. Health Check Endpoint**
- **What**: Add `/__health` route that returns 200 OK
- **Where**: `runserver.py` or `app_factory.py`, add new route
- **Why**: Useful for container orchestration (Kubernetes, ECS)
- **Difficulty**: One-line route

#### MODERATE (Requires Understanding Architecture)

**6. Redis Backend for Horizontal Scaling**
- **What**: Replace global `chatlines`, `chatters` with Redis
- **Where**: Create new `storage.py` module, refactor `runserver.py`
- **Why**: Allow multiple server instances behind load balancer
- **Difficulty**: Requires Redis knowledge, serialization, refactoring globals
- **Key Files**: `runserver.py:30-32` (global state), all message CRUD operations

**7. Rate Limiting**
- **What**: Limit messages per user per minute (e.g., 10 msg/min)
- **Where**: Add decorator to `chat_messages()` route (`runserver.py:283`)
- **Why**: Prevent spam/DoS
- **Difficulty**: Need sliding window or token bucket algorithm, session tracking
- **Libraries**: `flask-limiter` or custom implementation

**8. File Upload Support**
- **What**: Allow users to share files (images, documents) in chat
- **Where**: New route `/<path>/upload`, store in memory (< 10MB limit)
- **Why**: Useful for sharing screenshots, docs
- **Difficulty**: File handling, MIME type validation, memory management
- **Security**: Strict file size limits, no execution, virus scanning?

**9. Improved PGP Key Management**
- **What**: Allow users to import/export PGP keys via web interface
- **Where**: New route `/<path>/pgp/keys`, use `python-gnupg` library
- **Why**: Easier onboarding for encryption
- **Difficulty**: GPG library integration, key storage (in-memory), UI design
- **Key Files**: `email_system.py` (already has PGP stub), `PGP_USAGE.md`

**10. WebSocket Support for Real-Time Chat**
- **What**: Replace polling with WebSocket connections
- **Where**: Use `flask-socketio`, refactor JavaScript client
- **Why**: Lower latency, less server load than polling
- **Difficulty**: New library, event-driven architecture, testing
- **Considerations**: WebSocket over Tor can be tricky (latency, disconnects)

#### DIFFICULT (Architectural Changes)

**11. Multi-Room Support**
- **What**: Allow creating multiple chat rooms per server instance
- **Where**: Refactor routing to include room ID in path, separate `chatlines` per room
- **Why**: One server, many isolated conversations
- **Difficulty**: Routing overhaul, room management, memory partitioning
- **Key Changes**: 
  - Route: `/<path>/room/<room_id>/chats`
  - Storage: `chatlines_by_room = {room_id: [messages]}`
  - UI: Room creation/joining interface

**12. Voice/Video Chat (WebRTC)**
- **What**: Add peer-to-peer audio/video via WebRTC
- **Where**: New JavaScript module, STUN/TURN server setup (or use public ones)
- **Why**: Full communication suite
- **Difficulty**: WebRTC is complex, NAT traversal, Tor compatibility issues
- **Challenge**: WebRTC reveals IP addresses (defeats Tor anonymity unless carefully configured)

**13. Mobile App (React Native or Flutter)**
- **What**: Native iOS/Android app that connects to .onion backend
- **Where**: New repo, use Tor libraries for mobile (Orbot integration)
- **Why**: Better UX than mobile browser
- **Difficulty**: Mobile Tor integration is tricky, UI/UX design, app store issues

**14. Federated Server Discovery**
- **What**: Servers announce themselves to a directory, users can browse/join
- **Where**: New discovery service (separate server), add discovery routes
- **Why**: Find active chat servers without manual URL sharing
- **Difficulty**: Centralization vs anonymity trade-off, directory spam prevention
- **Security**: Directory could be honeypot or leak metadata

**15. Persistent Identity (Optional Mode)**
- **What**: Allow users to create persistent identities with keys
- **Where**: New user management system, key storage (encrypted on disk?)
- **Why**: Some users want reputation/continuity
- **Difficulty**: Conflicts with core ephemerality design, key management, authentication
- **Trade-off**: Persistent identity reduces anonymity (users are now linkable across sessions)

### Important Code Locations

**Starting Points for Common Tasks**:

| Task | File | Line Range | Notes |
|------|------|------------|-------|
| Add new chat route | `runserver.py` or `chat_routes.py` | 246-368 | Use existing routes as template, verify current line numbers |
| Add new email feature | `email_routes.py` | 1-150 | Or add to `runserver.py:372-848` |
| Modify chat UI | `templates/drop.html` | 1-200 | Separate script/noscript sections |
| Change message expiry | `runserver.py` | 56 | `check_older_than()` function default parameter |
| Add security feature | `email_security_tools.py` | 1-300 | Spoofing/phishing tools |
| Modify Tor setup | `runserver.py` | 850-906 | `main()` function |
| Add test | `tests/e2e.spec.js` | 1-200 | Playwright test suites |
| Change Docker setup | `Dockerfile`, `docker-compose.yml` | - | Container configuration |
| Add CI/CD check | `.github/workflows/` | - | GitHub Actions YAML |

**Key Functions to Understand**:

- `id_generator()` (`runserver.py:38-52`): Random ID generation
- `check_older_than()` (`runserver.py:56-64`): Message expiry logic
- `process_chat()` (`runserver.py:151-175`): Message wrapping and PGP handling
- `remove_headers()` (`runserver.py:179-183`): Security header stripping
- `chat_messages()` (`runserver.py:283-325`): Main chat POST/GET handler
- `main()` (`runserver.py:850-906`): Tor hidden service creation
- `EmailStorage.add_email()` (`email_system.py:40-60`): Email storage
- `BurnerEmailManager.generate_burner_email()` (`email_system.py:210-250`): Burner email creation

**Configuration Locations**:

- Python dependencies: `requirements.txt`
- Package metadata: `setup.py`
- Docker config: `Dockerfile`, `docker-compose.yml`
- Tor config: `torrc`
- Test config: `playwright.config.js`, `pytest.ini`
- CI/CD: `.github/workflows/*.yml`

### Development Tips

**1. Use Docker for Isolation**
- Avoid polluting your system with Tor configs
- `docker-compose up` gives you a clean environment every time

**2. Test with Tor Browser**
- Download Tor Browser (https://www.torproject.org/download/)
- Set to "Safest" mode to test noscript functionality
- Test script mode with "Safer" or custom settings

**3. Watch the Logs**
- Flask outputs requests to console
- Check for 404s (common when URL path mismatches)
- Tor connection errors are logged with `[*]` prefix

**4. Use Browser DevTools Over Tor**
- Tor Browser includes Firefox DevTools
- Check Network tab for AJAX polling (`chatsjs` endpoint)
- Console tab shows JavaScript errors

**5. Mock the Tor Dependency**
- For unit tests, you can mock `stem.Controller`
- See `tests/mock_server.py` for examples
- Avoids needing Tor running for every test

**6. Read Existing Tests**
- Playwright tests show expected user flows
- Good for understanding how features are supposed to work
- Copy test patterns for new features

**7. Check GitHub Issues**
- Look for issues labeled "good first issue" or "help wanted"
- See what features are planned vs. what's rejected
- Ask questions in issues before starting big changes

### Contributing Workflow

1. **Fork the repo** on GitHub
2. **Create a branch**: `git checkout -b feature/my-cool-feature`
3. **Make changes** and test locally
4. **Run tests**: `npm test`
5. **Commit with clear messages**: `git commit -m "Add markdown support to chat"`
6. **Push to your fork**: `git push origin feature/my-cool-feature`
7. **Open Pull Request** on GitHub
8. **Respond to feedback** from maintainers

See `CONTRIBUTING.md` for detailed guidelines.

### Documentation to Read

**Before Coding**:
- `README.md` - Feature overview
- `INSTALL.md` - Deployment options
- `SECURITY.md` - Security model and limitations
- `TESTING.md` - How to run tests

**For Specific Features**:
- `PGP_USAGE.md` - PGP encryption setup
- `EMAIL_SYSTEM.md` - Email features documentation
- `DOMAIN_API_SETUP.md` - Domain rotation setup
- `DOCKER.md` - Docker deployment
- `QUADLETS.md` - Systemd integration
- `AWS_DEPLOYMENT.md` - Cloud deployment

**For Maintainers**:
- `CONTRIBUTING.md` - Contribution guidelines
- `CODE_OF_CONDUCT.md` - Community standards
- `CHANGELOG.md` - Version history
- `CICD_REVIEW_SUMMARY.md` - CI/CD pipeline details

### Gotchas and Common Issues

**1. Tor Connection Fails**
- **Error**: `[!] Tor proxy or Control Port are not running`
- **Fix**: Start Tor with `tor --ControlPort 9051 --CookieAuthentication 0`
- **Or**: Use Docker Compose (handles Tor automatically)

**2. Hidden Service Takes Forever to Publish**
- **Cause**: Tor network is slow, or your relay choice is poor
- **Fix**: Wait 1-2 minutes. If still failing, restart Tor.

**3. 404 on All Routes**
- **Cause**: URL path mismatch (random path is checked on every route)
- **Fix**: Ensure you're using the exact URL printed by server

**4. Messages Not Appearing**
- **Cause**: Messages expired (> 180 seconds old)
- **Fix**: Send new messages, or increase expiry time

**5. Session Lost Between Requests**
- **Cause**: Cookies disabled, or session key changed (server restart)
- **Fix**: Enable cookies in browser, don't restart server mid-session

**6. PGP Messages Look Garbled**
- **Cause**: Sanitization or wrapping broke the PGP format
- **Fix**: Ensure PGP detection logic is working (`-----BEGIN PGP MESSAGE-----`)

**7. Tests Fail with "Browser Not Found"**
- **Cause**: Playwright browsers not installed
- **Fix**: `npx playwright install`

**8. Docker Container Can't Connect to Tor**
- **Cause**: Networking issue between containers
- **Fix**: Check `docker-compose.yml` network config, ensure `tor` service is healthy

### Performance Considerations

**Current Bottlenecks**:
- **Tor Latency**: Hidden services add 3-5 seconds per request (network overhead)
- **Polling**: JavaScript mode polls every 2 seconds (wasteful)
- **No Caching**: Every request re-renders template
- **Global State**: Single-threaded cleanup loop on every request

**Optimization Ideas**:
- Use WebSockets to eliminate polling
- Add Redis for distributed state
- Implement message pagination (only load recent messages)
- Use Jinja2 template caching
- Add rate limiting to reduce abuse

### Security Best Practices for Contributors

**1. Never Store Sensitive Data on Disk**
- Keep the in-memory design
- If you must persist, encrypt with user-provided key

**2. Validate All User Input**
- Sanitize chat messages
- Validate email addresses
- Limit file uploads (if added)

**3. Don't Log Sensitive Info**
- No logging of messages, user IDs, or .onion addresses
- Only log errors and system events

**4. Test for XSS**
- Any new input field must be tested for XSS
- Use Playwright tests to verify sanitization

**5. Review Tor Implications**
- Some features (WebRTC, WebSockets) can leak real IP
- Research before adding network features

**6. Use `secrets` for Crypto**
- If adding authentication tokens, use `secrets.token_hex()`
- Don't use `random` for security-critical values

### Resources and References

**Tor Development**:
- Tor Project Docs: https://2019.www.torproject.org/docs/documentation.html.en
- stem Library Docs: https://stem.torproject.org/
- Hidden Service Protocol: https://spec.torproject.org/rend-spec/

**Flask Development**:
- Flask Docs: https://flask.palletsprojects.com/
- Blueprint Pattern: https://flask.palletsprojects.com/en/latest/blueprints/
- Session Management: https://flask.palletsprojects.com/en/latest/quickstart/#sessions

**Security**:
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- PGP Best Practices: https://riseup.net/en/security/message-security/openpgp/best-practices
- Tor Security: https://support.torproject.org/

**Testing**:
- Playwright Docs: https://playwright.dev/
- pytest Docs: https://docs.pytest.org/

---

## Quick Reference: Important Commands

```bash
# Development
python runserver.py                    # Start server (needs Tor running)
tor --ControlPort 9051 --CookieAuthentication 0  # Start Tor with control port

# Docker
./compose-up.sh                        # Start with Docker Compose
./compose-down.sh                      # Stop and clean up

# Testing
npm test                               # Run all tests
npm run test:headless                  # Headless tests only
npx playwright test --headed           # Visible browser (debugging)

# Deployment
./install-quadlets.sh                  # Install systemd units
systemctl --user start opsechat-app    # Start as systemd service
podman build -t localhost/opsechat:latest .  # Build container

# AWS
aws cloudformation create-stack --stack-name opsechat-infrastructure-production \
  --template-body file://aws/cloudformation/opsechat-infrastructure.yml
```

---

**Welcome to OpSecChat! Whether you're fixing a bug, adding a feature, or just exploring, this guide should help you navigate the codebase. If you get stuck, open an issue or check existing documentation. Happy hacking! 🚀**
