// @ts-check
/**
 * Playwright config for the container-up-to-container-down E2E.
 *
 * Run separately by `scripts/test-compose-e2e.sh` AFTER `compose-up.sh`
 * has the stack healthy. Drives the same alpha specs as the default config,
 * but against the localhost admin proxy on 127.0.0.1:8080 instead of
 * spinning a new Flask process.
 */
const { defineConfig, devices } = require('@playwright/test');

const BASE_URL = process.env.OPSECHAT_BASE_URL || 'http://127.0.0.1:8080';

module.exports = defineConfig({
  testDir: './tests/alpha',
  // Skip specs that need direct Flask access (rate-limit hammering against
  // the admin proxy is unkind and noisy; we exercise rate limits separately).
  testIgnore: ['rate_limits_and_errors.spec.js', 'visual_walkthrough.spec.js'],
  fullyParallel: false,
  workers: 1,
  retries: 1,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI ? 'line' : 'list',

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
  ],

  // No webServer here -- the compose stack is brought up by the wrapper script.
});
