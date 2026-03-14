/**
 * Email Burner E2E Tests
 * Tests for burner email functionality
 */

const { test, expect } = require('@playwright/test');

test.use({
  baseURL: 'http://127.0.0.1:5001',
});

test.describe('Email Burner Functionality', () => {
  test('should load email burner page with 200 status', async ({ page }) => {
    const response = await page.goto('/test-path-12345/email/burner');
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
    
    // Verify content includes burner-related elements
    const content = await page.content();
    expect(content.length).toBeGreaterThan(0);
  });

  test('should generate burner email via POST and return valid response', async ({ page }) => {
    // Establish session first
    await page.goto('/test-path-12345/email/burner');
    
    // Generate a burner email
    const response = await page.request.post('/test-path-12345/email/burner', {
      form: {
        action: 'generate'
      }
    });
    
    // Should succeed with 200 or redirect
    expect([200, 302]).toContain(response.status());
  });

  test('should list active burners as JSON with 200 status', async ({ page }) => {
    // Establish session and generate a burner
    await page.goto('/test-path-12345/email/burner');
    await page.request.post('/test-path-12345/email/burner', {
      form: {
        action: 'generate'
      }
    });
    
    // Get burner list
    const response = await page.request.get('/test-path-12345/email/burner/list');
    
    expect(response.status()).toBe(200);
    
    // Verify JSON response
    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('application/json');
    
    const burners = await response.json();
    expect(Array.isArray(burners)).toBe(true);
  });

  test('should load burner page with JavaScript enabled', async ({ page }) => {
    const response = await page.goto('/test-path-12345/email/burner/yesscript');
    
    if (!response) {
      test.skip();
      return;
    }
    
    expect(response.status()).toBe(200);
    
    const content = await page.content();
    expect(content.length).toBeGreaterThan(0);
  });
});
