// @ts-check
/**
 * Opt-in Playwright configuration for legacy specs in `tests/legacy/`.
 *
 * These specs target the mock test server and cover features that are NOT
 * part of the alpha shipping surface (legacy chat, email, burner emails,
 * etc.). Run with:  npx playwright test --config=playwright-legacy.config.js
 */
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/legacy',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',

  use: {
    baseURL: 'http://127.0.0.1:5001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium-headless',
      use: { ...devices['Desktop Chrome'], headless: true },
    },
  ],

  webServer: {
    command: 'python3 tests/mock_server.py',
    url: 'http://127.0.0.1:5001/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
