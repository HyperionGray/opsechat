// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
  testDir: './tests',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: 'http://127.0.0.1:5000',
    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium-headless',
      use: { 
        ...devices['Desktop Chrome'],
        headless: true,
      },
    },

    {
      name: 'firefox-headless',
      use: { 
        ...devices['Desktop Firefox'],
        headless: true,
      },
    },

    {
      name: 'webkit-headless',
      use: { 
        ...devices['Desktop Safari'],
        headless: true,
      },
    },

    /* Headed browser configurations for manual testing/debugging */
    {
      name: 'chromium-headed',
      use: { 
        ...devices['Desktop Chrome'],
        headless: false,
      },
    },

    {
      name: 'firefox-headed',
      use: { 
        ...devices['Desktop Firefox'],
        headless: false,
      },
    },
  ],

  /* Run your local dev server before starting the tests */
  // Note: The server must be started manually for these tests
  // since it requires Tor to be running
});
