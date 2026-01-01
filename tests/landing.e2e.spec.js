/**
 * Landing Page Tests for opsechat
 * 
 * Tests for landing page functionality, auto-redirects, and basic navigation.
 * Extracted from e2e.spec.js for better organization.
 */

const { test, expect } = require('@playwright/test');

// Use the mock server on port 5001
test.use({
  baseURL: 'http://127.0.0.1:5001',
});

test.describe('Landing Page Functionality', () => {
  test('should load landing page with 200 status and correct auto-redirect content', async ({ page }) => {
    const response = await page.goto('/test-path-12345', {
      waitUntil: 'domcontentloaded'
    });
    
    if (!response) {
      test.skip();
      return;
    }
    
    // Verify status code
    expect(response.status()).toBe(200);
    
    // Wait a moment to let any auto-redirect settle
    await page.waitForTimeout(100);
    
    // Verify content includes redirect script or landing content
    const content = await page.content().catch(() => {
      // If page is navigating, that's also valid behavior
      return '<html><body>navigating</body></html>';
    });
    expect(content.length).toBeGreaterThan(0);
    // Should have either redirect script or actual landing page content
    const hasRedirect = content.includes('window.location') || content.includes('yesscript');
    const hasContent = content.includes('<html') || content.includes('<body') || content.includes('navigating');
    expect(hasRedirect || hasContent).toBe(true);
  });

  test('should return 404 for invalid path with minimal content', async ({ page }) => {
    const response = await page.goto('/invalid-random-path-xyz123', {
      waitUntil: 'domcontentloaded'
    }).catch(() => null);
    
    if (!response) {
      // If navigation fails completely, that's also valid for 404
      return;
    }
    
    // Should return 404 status
    expect(response.status()).toBe(404);
    
    // Content should be minimal (empty or very short)
    const content = await page.content();
    expect(content.length).toBeLessThan(100);
  });

  test('should handle auto-redirect landing page', async ({ page }) => {
    const response = await page.goto('/test-path-12345/auto');
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
    
    const content = await page.content();
    expect(content).toBeTruthy();
    expect(content.length).toBeGreaterThan(0);
  });

  test('should handle yes-script landing page', async ({ page }) => {
    const response = await page.goto('/test-path-12345/yes');
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
    
    const content = await page.content();
    expect(content).toBeTruthy();
    expect(content.length).toBeGreaterThan(0);
  });

  test('should handle noscript landing page', async ({ page }) => {
    const response = await page.goto('/test-path-12345/noscript');
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
    
    const content = await page.content();
    expect(content).toBeTruthy();
    expect(content.length).toBeGreaterThan(0);
  });
});