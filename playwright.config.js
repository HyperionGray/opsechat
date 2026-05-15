// @ts-check
/**
 * Playwright configuration for the OpSecChat alpha test suite.
 *
 * Default suite drives the *real* Flask app (`tests/real_app_server.py`)
 * across chromium/firefox/webkit headless. Headed and slow-mo projects are
 * available locally; CI auto-skips them.
 *
 * Legacy specs (mock-server based, non-alpha surface) live in tests/legacy/
 * and are run via `playwright-legacy.config.js`.
 */
const { defineConfig, devices } = require('@playwright/test');

const PORT = Number(process.env.OPSECHAT_PLAYWRIGHT_PORT || 5111);
const BASE_URL = process.env.OPSECHAT_BASE_URL || `http://127.0.0.1:${PORT}`;

const HEADED_PROJECTS = process.env.CI
  ? []
  : [
      {
        name: 'chromium-headed',
        testMatch: ['**/*.spec.js'],
        use: {
          ...devices['Desktop Chrome'],
          headless: false,
        },
      },
      {
        // Visual walkthrough project: only runs the dedicated narration spec
        // and adds slow-mo + a sane viewport so a human can sit and watch.
        name: 'chromium-headed-slowmo',
        testMatch: ['**/visual_walkthrough.spec.js'],
        use: {
          ...devices['Desktop Chrome'],
          headless: false,
          viewport: { width: 1400, height: 900 },
          launchOptions: { slowMo: 350 },
        },
      },
    ];

module.exports = defineConfig({
  testDir: './tests',
  // Only run alpha-scope specs by default. basic.spec.js is structural and
  // covers the project layout; tests/alpha/ are the real-app E2E specs.
  testMatch: ['basic.spec.js', 'alpha/*.spec.js'],
  testIgnore: ['legacy/**', 'manual/**'],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['line'], ['html', { open: 'never' }]] : 'html',
  timeout: 120_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium-headless',
      use: { ...devices['Desktop Chrome'], headless: true },
    },
    {
      name: 'firefox-headless',
      use: { ...devices['Desktop Firefox'], headless: true },
    },
    {
      name: 'webkit-headless',
      use: { ...devices['Desktop Safari'], headless: true },
    },
    ...HEADED_PROJECTS,
  ],

  // Boots the real Flask app (the same one users hit). Reuses an existing
  // server in dev so iterating on a single spec is fast.
  webServer: {
    command: 'python3 tests/real_app_server.py',
    url: `${BASE_URL}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      OPSECHAT_PLAYWRIGHT_PORT: String(PORT),
    },
  },
});
