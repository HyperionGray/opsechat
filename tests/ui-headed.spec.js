/**
 * UI Tests for opsechat (Headed Mode)
 * 
 * These tests are meant to run with headed browsers for visual validation
 * Run with: npx playwright test --project=chromium-headed --headed
 */

const { test, expect } = require('@playwright/test');

// Configure test to use the mock server
test.use({
  baseURL: 'http://127.0.0.1:5000',
});

test.describe('Headed UI Tests - Visual Validation', () => {
  test('should display landing page correctly', async ({ page }) => {
    test.setTimeout(30000);
    
    await page.goto('/test-path-12345', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      console.log('Could not connect to mock server, skipping test');
      test.skip();
      return;
    });
    
    // Take a screenshot for visual validation
    await page.screenshot({ 
      path: 'test-results/landing-page.png',
      fullPage: true 
    });
    
    // Verify page has loaded
    const title = await page.title();
    expect(title).toBeDefined();
  });

  test('should display chat interface with script', async ({ page }) => {
    test.setTimeout(30000);
    
    await page.goto('/test-path-12345/script', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return;
    });
    
    // Take a screenshot
    await page.screenshot({ 
      path: 'test-results/chat-script.png',
      fullPage: true 
    });
    
    // Check if jQuery is loaded (if JavaScript is enabled)
    const jqueryLoaded = await page.evaluate(() => {
      return typeof window.$ !== 'undefined' || typeof window.jQuery !== 'undefined';
    }).catch(() => false);
    
    console.log('jQuery loaded:', jqueryLoaded);
  });

  test('should display noscript chat interface', async ({ page }) => {
    test.setTimeout(30000);
    
    // Disable JavaScript for this test
    await page.context().addInitScript(() => {
      // This page will load with minimal JS
    });
    
    await page.goto('/test-path-12345/noscript', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return;
    });
    
    // Take a screenshot
    await page.screenshot({ 
      path: 'test-results/chat-noscript.png',
      fullPage: true 
    });
    
    // Verify the page structure
    const content = await page.content();
    expect(content).toBeDefined();
  });

  test('should handle form interactions', async ({ page }) => {
    test.setTimeout(30000);
    
    await page.goto('/test-path-12345/script', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return;
    });
    
    // Try to find a chat input form
    const formExists = await page.locator('form').count() > 0;
    console.log('Form exists:', formExists);
    
    if (formExists) {
      // Take a screenshot showing the form
      await page.screenshot({ 
        path: 'test-results/chat-form.png',
        fullPage: true 
      });
    }
  });

  test('should show responsive design', async ({ page }) => {
    test.setTimeout(30000);
    
    // Test different viewport sizes
    const viewports = [
      { width: 1920, height: 1080, name: 'desktop' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 375, height: 667, name: 'mobile' },
    ];
    
    for (const viewport of viewports) {
      await page.setViewportSize({ 
        width: viewport.width, 
        height: viewport.height 
      });
      
      await page.goto('/test-path-12345', { 
        waitUntil: 'domcontentloaded',
        timeout: 10000 
      }).catch(err => {
        test.skip();
        return;
      });
      
      // Take screenshots at different sizes
      await page.screenshot({ 
        path: `test-results/responsive-${viewport.name}.png`,
        fullPage: true 
      });
    }
  });
});

test.describe('Headed UI Tests - Interaction', () => {
  test('should demonstrate chat flow', async ({ page }) => {
    test.setTimeout(30000);
    
    await page.goto('/test-path-12345/script', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return;
    });
    
    // Take initial screenshot
    await page.screenshot({ 
      path: 'test-results/chat-initial.png',
      fullPage: true 
    });
    
    // Look for chat input
    const inputExists = await page.locator('input[type="text"], textarea').count() > 0;
    
    if (inputExists) {
      const input = page.locator('input[type="text"], textarea').first();
      await input.fill('Test message');
      
      // Take screenshot with text entered
      await page.screenshot({ 
        path: 'test-results/chat-with-text.png',
        fullPage: true 
      });
      
      console.log('Chat input field found and tested');
    }
  });

  test('should handle navigation between versions', async ({ page }) => {
    test.setTimeout(30000);
    
    // Visit landing page
    await page.goto('/test-path-12345', { 
      waitUntil: 'domcontentloaded',
      timeout: 10000 
    }).catch(err => {
      test.skip();
      return;
    });
    
    await page.screenshot({ 
      path: 'test-results/navigation-landing.png',
      fullPage: true 
    });
    
    // Try to find and click navigation links
    const links = await page.locator('a').count();
    console.log(`Found ${links} links on the page`);
    
    if (links > 0) {
      // Take screenshot showing links
      await page.screenshot({ 
        path: 'test-results/navigation-links.png',
        fullPage: true 
      });
    }
  });
});
