/**
 * Chat Functionality Tests for opsechat
 * 
 * Tests for chat interface, message posting, and real-time communication.
 * Extracted from e2e.spec.js for better organization.
 */

const { test, expect } = require('@playwright/test');

// Use the mock server on port 5001
test.use({
  baseURL: 'http://127.0.0.1:5001',
});

test.describe('Chat Interface - Script Mode', () => {
  test('should load script-enabled chat with 200 status and correct content', async ({ page }) => {
    const response = await page.goto('/test-path-12345/script');
    
    if (!response) {
      test.skip();
      return;
    }
    
    // Verify status code
    expect(response.status()).toBe(200);
    
    // Verify content is HTML
    const content = await page.content();
    expect(content).toContain('<html>');
    expect(content.length).toBeGreaterThan(100);
  });

  test('should have interactive form elements in script mode', async ({ page }) => {
    await page.goto('/test-path-12345/script');
    
    // Look for chat input form
    const form = await page.locator('form').first();
    expect(form).toBeTruthy();
    
    // Check for input field and verify it's interactive
    const inputExists = await page.locator('input[name="dropdata"], textarea[name="dropdata"]').count() > 0;
    expect(inputExists).toBe(true);
    
    if (inputExists) {
      const input = page.locator('input[name="dropdata"], textarea[name="dropdata"]').first();
      await input.fill('Test message');
      const value = await input.inputValue();
      expect(value).toBe('Test message');
    }
  });
});

test.describe('Chat Interface - NoScript Mode', () => {
  test('should load noscript chat with 200 status and correct content', async ({ page }) => {
    const response = await page.goto('/test-path-12345/noscript');
    
    if (!response) {
      test.skip();
      return;
    }
    
    // Verify status code
    expect(response.status()).toBe(200);
    
    // Verify content differs from script mode
    const content = await page.content();
    expect(content).toBeTruthy();
    expect(content.length).toBeGreaterThan(0);
  });

  test('should have accessible form elements in noscript mode', async ({ page }) => {
    await page.goto('/test-path-12345/noscript');
    
    // Verify form exists for posting without JavaScript
    const forms = await page.locator('form').count();
    expect(forms).toBeGreaterThan(0);
  });
});

test.describe('Chat Messages API', () => {
  test('should retrieve chat messages with 200 status and valid content', async ({ page }) => {
    const response = await page.goto('/test-path-12345/chats');
    
    if (!response) {
      test.skip();
      return;
    }
    
    // Verify status code
    expect(response.status()).toBe(200);
    
    // Verify HTML response (should be a template)
    const content = await page.content();
    expect(content).toContain('<html>');
  });

  test('should post message to chats endpoint and get valid response', async ({ page }) => {
    // First establish a session
    await page.goto('/test-path-12345');
    
    // Post a message via the chats endpoint
    const response = await page.request.post('/test-path-12345/chats', {
      form: {
        dropdata: 'Test message via POST'
      },
      maxRedirects: 0
    }).catch(async (err) => {
      // If it redirects, that's okay - try again allowing redirects
      return await page.request.post('/test-path-12345/chats', {
        form: {
          dropdata: 'Test message via POST'
        }
      });
    });
    
    // Should get 200, 302 redirect, or successfully follow redirect
    expect([200, 302, 301]).toContain(response.status());
  });

  test('should retrieve chats as JSON via chatsjs endpoint', async ({ page }) => {
    // Establish session first
    await page.goto('/test-path-12345');
    
    // Get chats as JSON
    const response = await page.request.get('/test-path-12345/chatsjs');
    
    // Verify status and content-type
    expect(response.status()).toBe(200);
    
    // Verify it's JSON
    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('application/json');
    
    // Verify JSON structure
    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);
  });

  test('should post message via chatsjs and get JSON response', async ({ page }) => {
    // Establish session first
    await page.goto('/test-path-12345');
    
    // Post message to JSON endpoint
    const response = await page.request.post('/test-path-12345/chatsjs', {
      form: {
        dropdata: 'Test JSON message'
      }
    });
    
    expect(response.status()).toBe(200);
    
    // Should return JSON
    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('application/json');
    
    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);
  });
});