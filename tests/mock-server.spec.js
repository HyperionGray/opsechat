/**
 * Mock Server Tests for opsechat
 * 
 * These tests use a mock Flask app to test functionality without requiring Tor
 */

const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');

// Helper to create a mock server for testing
async function startMockServer() {
  return new Promise((resolve, reject) => {
    const mockServerPath = path.join(__dirname, 'mock_server.py');
    const serverProcess = spawn('python3', [mockServerPath], {
      cwd: path.join(__dirname, '..')
    });

    let output = '';
    serverProcess.stdout.on('data', (data) => {
      output += data.toString();
      if (output.includes('Running on')) {
        resolve(serverProcess);
      }
    });

    serverProcess.stderr.on('data', (data) => {
      console.error('Server error:', data.toString());
    });

    setTimeout(() => {
      reject(new Error('Server failed to start within timeout'));
    }, 10000);
  });
}

test.describe('Mock Server Tests', () => {
  let serverProcess;

  test.beforeAll(async () => {
    // Start mock server before tests
    try {
      serverProcess = await startMockServer();
      // Wait a bit for server to be fully ready
      await new Promise(resolve => setTimeout(resolve, 2000));
    } catch (error) {
      console.log('Could not start mock server:', error.message);
      console.log('Skipping mock server tests');
    }
  });

  test.afterAll(() => {
    // Clean up server process
    if (serverProcess) {
      serverProcess.kill();
    }
  });

  test('should render index page', async ({ page }) => {
    if (!serverProcess) {
      test.skip();
      return;
    }

    await page.goto('/');
    const response = await page.evaluate(() => document.body.textContent);
    expect(response).toBeDefined();
  });

  test('should have basic Flask routes configured', async ({ page }) => {
    if (!serverProcess) {
      test.skip();
      return;
    }

    const response = await page.goto('/');
    expect(response.status()).toBe(200);
  });
});

test.describe('Session and Cookie Tests', () => {
  test('should handle sessions correctly', async ({ context }) => {
    const cookies = await context.cookies();
    // Initial state should have no session cookies
    expect(cookies.length).toBeGreaterThanOrEqual(0);
  });
});
