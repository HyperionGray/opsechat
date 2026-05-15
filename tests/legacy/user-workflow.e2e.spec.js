/**
 * User Workflow E2E Tests
 * Tests for complete user workflows and concurrent usage
 */

const { test, expect } = require('@playwright/test');

test.use({
  baseURL: 'http://127.0.0.1:5001',
});

test.describe('User Workflow - Complete Chat Session', () => {
  test('should complete full user chat workflow: visit, post, read', async ({ page }) => {
    // Step 1: User visits landing page
    let response = await page.goto('/test-path-12345');
    expect(response.status()).toBe(200);
    
    // Step 2: User navigates to script chat
    response = await page.goto('/test-path-12345/script');
    expect(response.status()).toBe(200);
    
    // Step 3: User posts a message
    const testMessage = 'Hello from complete workflow test!';
    response = await page.request.post('/test-path-12345/chatsjs', {
      form: {
        dropdata: testMessage
      }
    });
    expect(response.status()).toBe(200);
    
    // Step 4: User retrieves chat messages
    response = await page.request.get('/test-path-12345/chatsjs');
    expect(response.status()).toBe(200);
    
    const chats = await response.json();
    expect(Array.isArray(chats)).toBe(true);
    
    // Step 5: Verify user's message appears in chat
    const userMessage = chats.find(chat => chat.msg && chat.msg.includes(testMessage));
    expect(userMessage).toBeDefined();
    expect(userMessage.msg).toContain(testMessage);
  });
});

test.describe('Concurrent Users Simulation', () => {
  test('should handle multiple users posting messages', async ({ browser }) => {
    // Create two separate browser contexts (simulating two users)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();
    
    const page1 = await context1.newPage();
    const page2 = await context2.newPage();
    
    try {
      // User 1 visits and posts
      await page1.goto('/test-path-12345');
      const response1 = await page1.request.post('/test-path-12345/chatsjs', {
        form: {
          dropdata: 'Message from User 1'
        }
      });
      expect(response1.status()).toBe(200);
      
      // User 2 visits and posts
      await page2.goto('/test-path-12345');
      const response2 = await page2.request.post('/test-path-12345/chatsjs', {
        form: {
          dropdata: 'Message from User 2'
        }
      });
      expect(response2.status()).toBe(200);
      
      // Both users should see both messages
      const chatsResponse = await page1.request.get('/test-path-12345/chatsjs');
      const chats = await chatsResponse.json();
      
      const user1Msg = chats.find(c => c.msg && c.msg.includes('Message from User 1'));
      const user2Msg = chats.find(c => c.msg && c.msg.includes('Message from User 2'));
      
      expect(user1Msg).toBeDefined();
      expect(user2Msg).toBeDefined();
      
      // Users should have different IDs
      expect(user1Msg.username).not.toBe(user2Msg.username);
      
    } finally {
      await context1.close();
      await context2.close();
    }
  });
});
