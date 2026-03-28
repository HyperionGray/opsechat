# Development Guide

This guide helps developers set up their development environment and understand the codebase structure.

## Quick Start for Developers

### Prerequisites
- Python 3.8+
- Node.js 16+ (for testing)
- Podman or Docker (optional, for containerized development)
- Git

### Cursor Cloud Environment

This repository includes a checked-in Cursor Cloud environment at `.cursor/environment.json`.
It bootstraps a project-local virtual environment, installs Python and Node dependencies,
and caches Playwright browsers for future agents.

You can run the same bootstrap locally:

```bash
./scripts/bootstrap-dev-environment.sh
```

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/HyperionGray/opsechat.git
cd opsechat

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install test dependencies
npm install
npx playwright install

# Run the development server
python runserver.py
```

## Project Structure

```
opsechat/
├── src/                    # Python source modules (WIP - being organized)
│   └── tui/               # Terminal UI implementation
├── templates/             # Jinja2 HTML templates
├── static/                # Static assets (CSS, JS)
├── tests/                 # Test files (Playwright E2E + Python unit)
├── docs/                  # All documentation
│   ├── setup/            # Installation and deployment guides
│   ├── user-guide/       # User-facing documentation
│   ├── development/      # Developer resources
│   └── assessment/       # Code reviews and assessments
├── scripts/               # Utility scripts
├── aws/                   # AWS deployment templates
└── quadlets/              # Systemd quadlet files
```

## Development Tools

### Python Files in Root (Dev Tools)
These are development and testing utilities that help during development:

- **`manual-test.py`** - Manual testing script for interactive testing
- **`simple_test.py`** - Quick sanity checks
- **`quick_import_test.py`** - Test Python imports
- **`review_performance.py`** - Performance benchmarking tool
- **`usability_assessment.py`** - UI/UX testing helper
- **`comprehensive_functionality_test.py`** - Full functional test suite

### JavaScript/Shell Debug Utilities
- Deprecated one-off debug scripts (`test-ci-fix.js`, `test-server.js`, `test_fix.sh`) were removed during repository cleanup.
- Use documented workflows in `tests/` and `docs/user-guide/TESTING.md` instead.

### Main Application Files
- **`runserver.py`** - Main entry point (legacy monolithic)
- **`runserver_refactored.py`** - Refactored version (blueprint-based)
- **`app_factory.py`** - Flask app factory pattern
- **`chat-room.py`** - Standalone chat room creator
- **`tui-server.py`** - Terminal UI server
- **`tui-client.py`** - Terminal UI client
- **`domain_rotation_cli.py`** - CLI for domain management

### Route Modules (Blueprints)
- **`chat_routes.py`** - Chat functionality
- **`simple_chat_routes.py`** - Simplified chat interface
- **`email_routes.py`** - Email inbox/compose
- **`burner_routes.py`** - Burner email system
- **`security_routes.py`** - Security testing tools
- **`landing_routes.py`** - Landing pages
- **`review_routes.py`** - User review system

### Core Modules
- **`utils.py`** - Shared utility functions
- **`email_system.py`** - Email storage and PGP handling
- **`email_transport.py`** - SMTP/IMAP integration
- **`email_security_tools.py`** - Spoofing/phishing detection
- **`domain_manager.py`** - Domain registrar API integration
- **`state_manager.py`** - State persistence
- **`monitoring.py`** - Performance monitoring
- **`performance_utils.py`** - Performance utilities

## Testing

### Running Tests

```bash
# Run all Playwright tests (requires npm install)
npm test

# Run headless tests
npm run test:headless

# Run with visible browser
npm run test:headed

# Run Python unit tests (requires pytest)
python -m pytest

# Run specific test file
npx playwright test tests/basic.spec.js
```

### Test Organization
- **E2E Tests**: `tests/*.e2e.spec.js` - End-to-end browser tests
- **Unit Tests**: `tests/test_*.py` - Python unit tests
- **Mock Server**: `tests/mock_server.py` - Test server for isolated testing

## Code Quality

### Linting
```bash
# Python linting (if configured)
flake8 *.py

# JavaScript linting (if configured)
npm run lint
```

### Security Scanning
```bash
# Run security checks
./scripts/security-scan.sh
```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   npm test
   python -m pytest
   ```

4. **Commit with descriptive messages**
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## Key Architectural Decisions

### In-Memory Storage
- All data (chats, emails, sessions) stored in Python dictionaries
- Nothing written to disk except application code
- Messages auto-expire (3 minutes for chat)
- Memory overwriting on deletion for security

### Ephemeral Hidden Services
- Each server start creates new .onion address
- No persistent Tor keys
- Tor control via `stem` library

### Security-First Design
- No user accounts (randomized session IDs)
- No metadata logging
- Text-only (no file uploads)
- Emoji restrictions (skull only)
- CSP headers
- Input sanitization

## Common Development Tasks

### Adding a New Route
1. Create or modify route in appropriate `*_routes.py` file
2. Register in `app_factory.py` if needed
3. Create template in `templates/`
4. Add tests in `tests/`

### Adding a New Template
1. Create HTML file in `templates/`
2. Use consistent terminal-style theme (black bg, green text)
3. Minimal JavaScript (progressive enhancement)
4. Include version in footer

### Debugging Tips
- Use `app.config['DEBUG'] = True` for detailed errors
- Check Flask logs for request details
- Use browser dev tools for JavaScript debugging
- Test with Tor Browser for .onion testing

## Environment Variables

- `TOR_CONTROL_PORT` - Tor control port (default: 9051)
- `PORT` - Flask server port (default: 5000)
- `FLASK_ENV` - Development/production mode

## Troubleshooting

### Common Issues

**ImportError: No module named X**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

**Tor connection failed**
- Start Tor: `tor --ControlPort 9051 --CookieAuthentication 1`
- Check Tor is running: `ps aux | grep tor`

**Tests failing**
- Install Playwright browsers: `npx playwright install`
- Check Node modules: `npm install`

**Port already in use**
- Change port: `PORT=5001 python runserver.py`
- Or kill existing process

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

## Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Tor Documentation](https://www.torproject.org/docs/)
- [Playwright Documentation](https://playwright.dev/)
- [Stem Documentation](https://stem.torproject.org/)

## Getting Help

- Check existing [issues](https://github.com/HyperionGray/opsechat/issues)
- Read the [README](../../README.md)
- Review [documentation](../README.md)
- Contact maintainers

---

**Last Updated:** 2026-03-03  
**Version:** 0.8.0-alpha
