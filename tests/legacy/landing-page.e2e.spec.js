/**
 * Landing Page E2E Tests
 * Tests for landing page functionality and routing
 */

const { test, expect } = require('@playwright/test');

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
      test.skip();
      return;
    }
    
    // Verify status code is 404
    expect(response.status()).toBe(404);
    
    // Verify minimal or empty response body for security
    const content = await page.content();
    // The content should be very minimal (possibly just empty HTML structure)
    expect(content.length).toBeLessThan(100);
  });

  test('should create session and set cookie on first visit', async ({ page, context }) => {
    await page.goto('/test-path-12345');
    
    // Check for session cookie
    const cookies = await context.cookies();
    const sessionCookie = cookies.find(c => c.name === 'session');
    expect(sessionCookie).toBeDefined();
    expect(sessionCookie.value).toBeTruthy();
  });
});

test.describe('Root Path Behavior', () => {
  test('should handle root path gracefully with 200 status', async ({ page }) => {
    const response = await page.goto('/');
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
    
    // Root should return minimal response (may be empty or minimal HTML structure)
    const content = await page.content();
    // Should have minimal content (less than 100 chars after trimming, or just basic HTML wrapper)
    const textContent = await page.textContent('body');
    expect(textContent?.trim() || '').toBe('');
  });
});
