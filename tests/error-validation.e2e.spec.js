/**
 * Error Handling and Content Validation E2E Tests
 * Tests for error handling and response validation
 */

const { test, expect } = require('@playwright/test');

test.use({
  baseURL: 'http://127.0.0.1:5001',
});

test.describe('Error Handling', () => {
  test('should handle empty message submission gracefully', async ({ page }) => {
    await page.goto('/test-path-12345');
    
    // Try to post empty message - mock server redirects on POST to /chats
    const response = await page.request.post('/test-path-12345/chats', {
      form: {
        dropdata: ''
      },
      maxRedirects: 0
    }).catch(async (err) => {
      // Follow redirect if needed
      return await page.request.post('/test-path-12345/chats', {
        form: {
          dropdata: ''
        }
      });
    });
    
    // Should not error, should redirect or return success
    expect([200, 302, 301]).toContain(response.status());
  });

  test('should handle whitespace-only message gracefully', async ({ page }) => {
    await page.goto('/test-path-12345');
    
    const response = await page.request.post('/test-path-12345/chats', {
      form: {
        dropdata: '   '
      },
      maxRedirects: 0
    }).catch(async (err) => {
      // Follow redirect if needed
      return await page.request.post('/test-path-12345/chats', {
        form: {
          dropdata: '   '
        }
      });
    });
    
    // Should handle gracefully
    expect([200, 302, 301]).toContain(response.status());
  });

  test('should return 404 for non-existent routes', async ({ page }) => {
    const response = await page.goto('/test-path-12345/nonexistent-endpoint', {
      waitUntil: 'domcontentloaded'
    }).catch(() => null);
    
    if (response) {
      expect(response.status()).toBe(404);
    }
  });
});

test.describe('Response Content Validation', () => {
  test('should return valid HTML structure on chat pages', async ({ page }) => {
    const response = await page.goto('/test-path-12345/script');
    
    if (!response) {
      test.skip();
      return;
    }
    
    const content = await page.content();
    
    // Verify basic HTML structure
    expect(content).toContain('<html');
    expect(content).toContain('</html>');
    expect(content).toContain('<head');
    expect(content).toContain('<body');
  });

  test('should return properly formatted JSON from API endpoints', async ({ page }) => {
    await page.goto('/test-path-12345');
    
    const response = await page.request.get('/test-path-12345/chatsjs');
    const contentType = response.headers()['content-type'];
    
    expect(contentType).toContain('application/json');
    
    // Verify JSON is parseable
    const json = await response.json();
    expect(json).toBeDefined();
    expect(Array.isArray(json)).toBe(true);
  });
});
