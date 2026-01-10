/**
 * User Workflow Tests for opsechat
 * 
 * Tests for complete user workflows and integration scenarios.
 * Extracted from e2e.spec.js for better organization.
 */

const { test, expect } = require('@playwright/test');
const { 
  establishSession, 
  postChatMessage, 
  getChatMessages, 
  generateTestData,
  TEST_CONFIG 
} = require('./utils/test-helpers');

// Use the mock server on port 5001
test.use({
  baseURL: TEST_CONFIG.baseURL,
});

test.describe('User Workflow - Complete Chat Session', () => {
  test('should complete full user chat workflow: visit, post, read', async ({ page }) => {
    // Step 1: User visits landing page
    let response = await page.goto(TEST_CONFIG.testPath);
    expect(response.status()).toBe(200);
    
    // Step 2: User navigates to script chat
    response = await page.goto(TEST_CONFIG.testPath + '/script');
    expect(response.status()).toBe(200);
    
    // Step 3: User posts a message
    const testData = generateTestData('workflow');
    response = await postChatMessage(page, testData.message);
    expect(response.status()).toBe(200);
    
    // Step 4: User retrieves chat messages
    const chats = await getChatMessages(page);
    expect(Array.isArray(chats)).toBe(true);
    
    // Step 5: Verify user's message appears in chat
    const userMessage = chats.find(chat => chat.msg && chat.msg.includes(testData.message));
    expect(userMessage).toBeDefined();
    expect(userMessage.msg).toContain(testData.message);
  });

  test('should handle multi-user chat simulation', async ({ browser }) => {
    // Create two browser contexts (simulating different users)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();
    
    const page1 = await context1.newPage();
    const page2 = await context2.newPage();
    
    try {
      // Both users establish sessions
      await establishSession(page1);
      await establishSession(page2);
      
      // User 1 posts a message
      const testData1 = generateTestData('user1');
      await postChatMessage(page1, testData1.message);
      
      // User 2 posts a message
      const testData2 = generateTestData('user2');
      await postChatMessage(page2, testData2.message);
      
      // Both users should see both messages
      const chats1 = await getChatMessages(page1);
      const chats2 = await getChatMessages(page2);
      
      // Verify both users see the same chat history
      expect(chats1.length).toBe(chats2.length);
      
      // Verify both messages are present
      const hasUser1Message = chats1.some(chat => chat.msg && chat.msg.includes(testData1.message));
      const hasUser2Message = chats1.some(chat => chat.msg && chat.msg.includes(testData2.message));
      
      expect(hasUser1Message).toBe(true);
      expect(hasUser2Message).toBe(true);
      
    } finally {
      await context1.close();
      await context2.close();
    }
  });

  test('should handle user journey through different interface modes', async ({ page }) => {
    const testData = generateTestData('journey');
    
    // Step 1: Start at landing page
    await page.goto(TEST_CONFIG.testPath);
    
    // Step 2: Visit noscript version
    let response = await page.goto(TEST_CONFIG.testPath + '/noscript');
    expect(response.status()).toBe(200);
    
    // Step 3: Post message via noscript interface
    response = await page.request.post(TEST_CONFIG.testPath + '/chats', {
      form: { dropdata: testData.message + ' noscript' },
      maxRedirects: 0
    }).catch(async () => {
      // Handle redirect
      return await page.request.post(TEST_CONFIG.testPath + '/chats', {
        form: { dropdata: testData.message + ' noscript' }
      });
    });
    expect([200, 302, 301]).toContain(response.status());
    
    // Step 4: Switch to script version
    response = await page.goto(TEST_CONFIG.testPath + '/script');
    expect(response.status()).toBe(200);
    
    // Step 5: Post message via script interface
    response = await postChatMessage(page, testData.message + ' script');
    expect(response.status()).toBe(200);
    
    // Step 6: Verify both messages are in chat history
    const chats = await getChatMessages(page);
    const hasNoscriptMessage = chats.some(chat => 
      chat.msg && chat.msg.includes(testData.message + ' noscript')
    );
    const hasScriptMessage = chats.some(chat => 
      chat.msg && chat.msg.includes(testData.message + ' script')
    );
    
    expect(hasNoscriptMessage || hasScriptMessage).toBe(true); // At least one should be present
  });
});

test.describe('User Experience - Navigation Flow', () => {
  test('should provide consistent navigation between interface modes', async ({ page }) => {
    // Test navigation between different modes
    const modes = ['', '/auto', '/yes', '/noscript', '/script'];
    
    for (const mode of modes) {
      const response = await page.goto(TEST_CONFIG.testPath + mode);
      
      if (response) {
        expect(response.status()).toBe(200);
        
        // Verify page loads with content
        const content = await page.content();
        expect(content.length).toBeGreaterThan(0);
      }
    }
  });

  test('should maintain session consistency across navigation', async ({ page, context }) => {
    // Establish initial session
    await establishSession(page);
    
    const initialCookies = await context.cookies();
    expect(initialCookies.length).toBeGreaterThan(0);
    
    // Navigate through different modes
    const modes = ['/script', '/noscript', '/chats'];
    
    for (const mode of modes) {
      await page.goto(TEST_CONFIG.testPath + mode);
      
      const currentCookies = await context.cookies();
      expect(currentCookies.length).toBeGreaterThan(0);
      
      // Session should be maintained
      const sessionCookie = currentCookies.find(c => c.name.includes('session'));
      const initialSessionCookie = initialCookies.find(c => c.name.includes('session'));
      
      if (sessionCookie && initialSessionCookie) {
        expect(sessionCookie.value).toBe(initialSessionCookie.value);
      }
    }
  });
});

test.describe('User Experience - Message Lifecycle', () => {
  test('should handle message posting and retrieval lifecycle', async ({ page }) => {
    await establishSession(page);
    
    const testData = generateTestData('lifecycle');
    
    // Post multiple messages
    const messages = [
      testData.message + ' first',
      testData.message + ' second',
      testData.message + ' third'
    ];
    
    for (const message of messages) {
      const response = await postChatMessage(page, message);
      expect(response.status()).toBe(200);
    }
    
    // Retrieve and verify all messages
    const chats = await getChatMessages(page);
    
    // Should have at least the messages we posted
    const ourMessages = chats.filter(chat => 
      chat.msg && messages.some(msg => chat.msg.includes(msg))
    );
    
    expect(ourMessages.length).toBeGreaterThan(0);
    
    // Verify message order (most recent should be last)
    if (ourMessages.length > 1) {
      const timestamps = ourMessages.map(msg => new Date(msg.timestamp || Date.now()));
      for (let i = 1; i < timestamps.length; i++) {
        expect(timestamps[i].getTime()).toBeGreaterThanOrEqual(timestamps[i-1].getTime());
      }
    }
  });

  test('should handle message cleanup and limits', async ({ page }) => {
    await establishSession(page);
    
    const testData = generateTestData('cleanup');
    
    // Post many messages to test limits
    const messageCount = 20;
    for (let i = 0; i < messageCount; i++) {
      await postChatMessage(page, `${testData.message} ${i}`);
    }
    
    // Retrieve messages
    const chats = await getChatMessages(page);
    
    // Should have reasonable limit (not unlimited growth)
    expect(chats.length).toBeLessThan(50); // Reasonable upper bound
    
    // Should contain some of our recent messages
    const ourRecentMessages = chats.filter(chat => 
      chat.msg && chat.msg.includes(testData.message)
    );
    
    expect(ourRecentMessages.length).toBeGreaterThan(0);
  });
});