// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Configuration for Product Release Tests
 * These tests don't require a running server - they check file structure, imports, etc.
 */
module.exports = defineConfig({
  testDir: './tests',
  testMatch: 'product-release.spec.js',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  
  use: {
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
    ...(process.env.CI ? [] : [
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
    ]),
  ],
  
  // No webServer needed for these tests
});
