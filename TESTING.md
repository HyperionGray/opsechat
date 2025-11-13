# Testing Guide for opsechat

This document describes how to run tests for the opsechat project.

## Overview

The project now includes comprehensive testing using Playwright for both headless and headed browser testing. Tests validate:

- Basic project structure
- Python module imports and functionality
- Flask routes and session handling
- UI behavior in different modes (script, noscript)
- Security headers
- Responsive design
- Input validation

## Prerequisites

1. **Python 3.8+** with dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. **Node.js and npm** (for Playwright):
   ```bash
   node --version  # Should be v14+ or higher
   npm --version
   ```

3. **Install test dependencies**:
   ```bash
   npm install
   npx playwright install
   npx playwright install-deps  # Install browser dependencies
   ```

## Test Structure

```
tests/
├── basic.spec.js          # Basic structure and module tests
├── mock-server.spec.js    # Mock server integration tests
├── ui-headless.spec.js    # UI tests in headless mode
├── ui-headed.spec.js      # UI tests in headed mode
└── mock_server.py         # Mock Flask server for testing
```

## Running Tests

### Quick Start

Run all tests:
```bash
npm test
```

### Headless Tests

Run tests in headless mode (no browser window):
```bash
npm run test:headless
```

This runs tests in Chromium, Firefox, and WebKit browsers in headless mode.

### Headed Tests

Run tests with visible browser window (for debugging):
```bash
npm run test:headed
```

### Specific Test Suites

Run only basic tests:
```bash
npm run test:basic
```

Run only UI tests:
```bash
npm run test:ui
```

### Running Specific Browsers

Run tests in Chromium only:
```bash
npx playwright test --project=chromium-headless
```

Run tests in Firefox only:
```bash
npx playwright test --project=firefox-headless
```

### Debugging Tests

Run tests in debug mode:
```bash
npx playwright test --debug
```

Run tests with UI mode (interactive):
```bash
npx playwright test --ui
```

## Mock Server

For tests that require a running server, use the mock server:

1. Start the mock server in a separate terminal:
   ```bash
   python3 tests/mock_server.py
   ```

2. Run the tests in another terminal:
   ```bash
   npm test
   ```

The mock server simulates the Flask application without requiring Tor, making it suitable for automated testing.

## Test Reports

After running tests, view the HTML report:
```bash
npm run test:report
```

Or:
```bash
npx playwright show-report
```

Test results and screenshots are saved in:
- `playwright-report/` - HTML test report
- `test-results/` - Screenshots and traces

## Writing New Tests

### Example Test Structure

```javascript
const { test, expect } = require('@playwright/test');

test.describe('My Test Suite', () => {
  test('should do something', async ({ page }) => {
    await page.goto('/');
    const title = await page.title();
    expect(title).toBeDefined();
  });
});
```

### Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **Set appropriate timeouts** for tests that might take longer
3. **Handle connection errors gracefully** - tests should skip if server is unavailable
4. **Take screenshots** for visual validation in headed tests
5. **Test security features** like header removal and session handling

## CI/CD Integration

To integrate with CI/CD pipelines:

```bash
# Install dependencies
npm ci
npx playwright install --with-deps

# Run tests
npm run test:headless
```

Set the `CI` environment variable to enable CI-specific settings:
```bash
CI=true npm test
```

## Troubleshooting

### Tests fail to connect to server

Make sure the mock server is running:
```bash
python3 tests/mock_server.py
```

### Browser installation issues

Reinstall Playwright browsers:
```bash
npx playwright install --force
npx playwright install-deps
```

### Port already in use

If port 5000 is already in use, stop the conflicting process or modify the mock server to use a different port.

### Missing dependencies

Install all Python dependencies:
```bash
pip install -r requirements.txt
```

Install all Node.js dependencies:
```bash
npm install
```

## Test Coverage

Current test coverage includes:

- ✅ Project structure validation
- ✅ Python module imports
- ✅ Flask route handling
- ✅ Session management
- ✅ Security headers
- ✅ Input validation
- ✅ UI rendering (script and noscript modes)
- ✅ Responsive design
- ✅ Form interactions

## Future Enhancements

Potential areas for additional testing:

- PGP encryption functionality
- Message expiration (3-minute timeout)
- Multi-user chat scenarios
- Performance testing
- Load testing
- Accessibility testing
- Cross-browser compatibility edge cases

## Support

For issues or questions about testing:
1. Check the [Playwright documentation](https://playwright.dev/)
2. Review the test files for examples
3. Check the GitHub issues for known problems
