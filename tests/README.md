# Test Suite

This directory contains the automated test suite for opsechat.

## Test Files

- **basic.spec.js** - Tests for project structure, file existence, and Python module imports
- **e2e.spec.js** - Comprehensive end-to-end tests validating complete user workflows with both status codes and content validation
- **mock-server.spec.js** - Integration tests that use a mock Flask server
- **ui-headless.spec.js** - UI tests that run in headless browser mode (no visible window)
- **ui-headed.spec.js** - UI tests that run in headed mode (with visible browser window) for visual validation
- **mock_server.py** - A lightweight Flask server that simulates opsechat without requiring Tor

## Running Tests

See the main [TESTING.md](../TESTING.md) file for detailed instructions on running tests.

Quick commands:
```bash
# Run all tests
npm test

# Run only headless tests
npm run test:headless

# Run only basic structure tests
npm run test:basic

# Run with visible browser (for debugging)
npm run test:headed

# Run end-to-end tests only
npm run test:e2e
```

## Mock Server

The mock server (`mock_server.py`) provides a test environment that doesn't require Tor to be running. It implements the same Flask routes as the main application but with simpler configuration.

To use the mock server:
```bash
python3 tests/mock_server.py
```

The server will run on http://localhost:5001 and can be used for manual testing or as a target for automated tests.

## Test Coverage

Current tests validate:
- ✅ Project file structure
- ✅ Python dependencies and imports
- ✅ Flask route handlers
- ✅ Session management
- ✅ Security headers (Server and Date removal)
- ✅ Multiple browser compatibility (Chromium, Firefox, WebKit)
- ✅ Responsive design
- ✅ Form interactions
- ✅ Chat functionality (both script and noscript modes)
- ✅ **Complete user workflows from landing to chat to message posting** (NEW)
- ✅ **HTTP status codes AND actual content validation** (NEW)
- ✅ **Email burner generation and management** (NEW)
- ✅ **PGP message preservation through sanitization** (NEW)
- ✅ **XSS attack prevention** (NEW)
- ✅ **Multi-user concurrent chat scenarios** (NEW)
- ✅ **JSON API endpoint validation** (NEW)

## Adding New Tests

To add a new test:

1. Create a new `.spec.js` file in this directory
2. Follow the Playwright test syntax:
   ```javascript
   const { test, expect } = require('@playwright/test');
   
   test.describe('My Test Suite', () => {
     test('should do something', async ({ page }) => {
       // Your test code here
     });
   });
   ```
3. Run the test: `npx playwright test tests/your-test.spec.js`

See the [Playwright documentation](https://playwright.dev/docs/intro) for more information.
