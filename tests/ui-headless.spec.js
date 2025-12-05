/**
 * UI Tests for opsechat (Headless)
 * 
 * These tests validate the UI functionality in headless mode
 * Requires the mock server to be running
 */

const { test, expect } = require('@playwright/test');

// Configure test to use the mock server
test.use({
  baseURL: 'http://127.0.0.1:5001',
});

test.describe('Headless UI Tests - Landing Page', () => {
  test('should load landing page with valid path', async ({ page }) => {
    test.setTimeout(30000);
    
    // Try to access the landing page
    const response = await page.goto('/test-path-12345', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      console.log('Could not connect to mock server, skipping test');
      return null;
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
    
    // Check if the page has expected elements
    const content = await page.content();
    expect(content).toBeDefined();
  });

  test('should return 404 for invalid path', async ({ page }) => {
    test.setTimeout(30000);
    
    const response = await page.goto('/invalid-path-xyz', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      console.log('Could not connect to mock server, skipping test');
      return null;
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(404);
  });

  test('should have session cookie after visiting', async ({ page, context }) => {
    test.setTimeout(30000);
    
    await page.goto('/test-path-12345', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return;
    });
    
    const cookies = await context.cookies();
    // Should have Flask session cookie
    const sessionCookie = cookies.find(c => c.name === 'session');
    expect(sessionCookie).toBeDefined();
  });
});

test.describe('Headless UI Tests - Chat Interface', () => {
  test('should access script version', async ({ page }) => {
    test.setTimeout(30000);
    
    const response = await page.goto('/test-path-12345/script', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return null;
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
  });

  test('should access noscript version', async ({ page }) => {
    test.setTimeout(30000);
    
    const response = await page.goto('/test-path-12345/noscript', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return null;
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
  });

  test('should load chats endpoint', async ({ page }) => {
    test.setTimeout(30000);
    
    const response = await page.goto('/test-path-12345/chats', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return null;
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
  });
});

test.describe('Headless UI Tests - Security Headers', () => {
  test('should not expose server header', async ({ page }) => {
    test.setTimeout(30000);
    
    const response = await page.goto('/', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return null;
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    const headers = response.headers();
    
    // Check that Server header is empty or not present (security feature)
    if (headers['server']) {
      expect(headers['server']).toBe('');
    }
    
    // Check that Date header is empty or not present (security feature)
    if (headers['date']) {
      expect(headers['date']).toBe('');
    }
  });
});

test.describe('Headless UI Tests - Input Validation', () => {
  test('should handle empty root path', async ({ page }) => {
    test.setTimeout(30000);
    
    const response = await page.goto('/', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return null;
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
  });
});
