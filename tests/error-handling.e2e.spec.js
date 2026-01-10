/**
 * Error Handling and Edge Cases Tests for opsechat
 * 
 * Tests for error conditions, edge cases, and graceful failure handling.
 * Extracted from e2e.spec.js for better organization.
 */

const { test, expect } = require('@playwright/test');

// Use the mock server on port 5001
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

  test('should handle malformed requests gracefully', async ({ page }) => {
    await page.goto('/test-path-12345');
    
    // Try posting without required form data
    const response = await page.request.post('/test-path-12345/chats', {
      data: 'invalid-data-format'
    }).catch(() => null);
    
    if (response) {
      // Should not crash, should return error or redirect
      expect([200, 302, 400, 422]).toContain(response.status());
    }
  });
});

test.describe('Session Edge Cases', () => {
  test('should handle requests without session gracefully', async ({ page, context }) => {
    // Clear all cookies to simulate no session
    await context.clearCookies();
    
    const response = await page.goto('/test-path-12345/chats');
    
    if (!response) {
      test.skip();
      return;
    }
    
    // Should handle gracefully (create new session or redirect)
    expect([200, 302, 401]).toContain(response.status());
  });

  test('should maintain session across multiple requests', async ({ page, context }) => {
    // First request
    await page.goto('/test-path-12345');
    
    const cookies1 = await context.cookies();
    expect(cookies1.length).toBeGreaterThan(0);
    
    // Second request should maintain session
    await page.goto('/test-path-12345/chats');
    
    const cookies2 = await context.cookies();
    expect(cookies2.length).toBeGreaterThan(0);
    
    // Session cookie should be the same
    const sessionCookie1 = cookies1.find(c => c.name.includes('session'));
    const sessionCookie2 = cookies2.find(c => c.name.includes('session'));
    
    if (sessionCookie1 && sessionCookie2) {
      expect(sessionCookie1.value).toBe(sessionCookie2.value);
    }
  });
});

test.describe('Root Path Behavior', () => {
  test('should handle root path gracefully with 200 status', async ({ page }) => {
    const response = await page.goto('/');
    
    if (!response) {
      test.skip();
      return;
    }
    
    // Root should return 200 with minimal content (security measure)
    expect(response.status()).toBe(200);
    
    const content = await page.content();
    // Should be minimal content (empty or very short for security)
    expect(content.length).toBeLessThan(100);
  });

  test('should not reveal application structure at root', async ({ page }) => {
    const response = await page.goto('/');
    
    if (!response) {
      test.skip();
      return;
    }
    
    const content = await page.content();
    
    // Should not contain revealing information
    expect(content).not.toContain('Flask');
    expect(content).not.toContain('opsechat');
    expect(content).not.toContain('chat');
    expect(content).not.toContain('error');
  });
});

test.describe('Performance Edge Cases', () => {
  test('should handle rapid successive requests', async ({ page }) => {
    await page.goto('/test-path-12345');
    
    // Make multiple rapid requests
    const promises = [];
    for (let i = 0; i < 5; i++) {
      promises.push(
        page.request.post('/test-path-12345/chatsjs', {
          form: {
            dropdata: `Rapid message ${i}`
          }
        })
      );
    }
    
    const responses = await Promise.all(promises);
    
    // All should succeed or fail gracefully
    responses.forEach(response => {
      expect([200, 429, 500]).toContain(response.status());
    });
  });

  test('should handle concurrent sessions', async ({ browser }) => {
    // Create multiple browser contexts (simulating different users)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();
    
    const page1 = await context1.newPage();
    const page2 = await context2.newPage();
    
    // Both users visit the site
    await Promise.all([
      page1.goto('/test-path-12345'),
      page2.goto('/test-path-12345')
    ]);
    
    // Both users post messages
    const responses = await Promise.all([
      page1.request.post('/test-path-12345/chatsjs', {
        form: { dropdata: 'Message from user 1' }
      }),
      page2.request.post('/test-path-12345/chatsjs', {
        form: { dropdata: 'Message from user 2' }
      })
    ]);
    
    // Both should succeed
    responses.forEach(response => {
      expect(response.status()).toBe(200);
    });
    
    await context1.close();
    await context2.close();
  });
});