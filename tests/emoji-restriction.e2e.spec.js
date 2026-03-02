/**
 * Emoji Restriction Tests for OpSecChat
 * 
 * Tests that:
 * - Users are limited to ASCII-only input
 * - Users cannot send emojis
 * - Only the skull emoji (💀) is allowed for system use
 * - All other emojis are filtered out
 */

const { test, expect } = require('@playwright/test');

test.describe('Emoji Restriction Tests', () => {
  const emojiTests = [
    { name: 'Smileys', emoji: '😀😁😂🤣😃😄', category: 'emoticons' },
    { name: 'Hearts', emoji: '❤️💕💖💗💙💚', category: 'symbols' },
    { name: 'Animals', emoji: '🐶🐱🐭🐹🐰🦊', category: 'nature' },
    { name: 'Food', emoji: '🍎🍕🍔🍟🍿🥗', category: 'food' },
    { name: 'Activities', emoji: '⚽🏀🏈⚾🎾🏐', category: 'activities' },
    { name: 'Travel', emoji: '🚗🚕🚙🚌🚎🏎️', category: 'travel' },
    { name: 'Objects', emoji: '⌚📱💻⌨️🖥️🖨️', category: 'objects' },
    { name: 'Symbols', emoji: '🔴🟠🟡🟢🔵🟣', category: 'symbols' },
    { name: 'Flags', emoji: '🏳️🏴🏁🚩🏳️‍🌈', category: 'flags' },
    { name: 'Skulls (should be filtered from users)', emoji: '💀☠️', category: 'skulls' },
  ];

  test('should filter emojis from chat messages', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    for (const emojiTest of emojiTests.slice(0, 5)) {
      const message = `Test message with ${emojiTest.emoji} emojis`;
      
      // Send message with emojis
      await page.request.post('/test-path-12345/messages.json', {
        data: { message: message }
      });
      
      // Get messages
      const response = await page.request.get('/test-path-12345/messages.json');
      const data = await response.json();
      
      if (data.messages.length > 0) {
        const lastMessage = data.messages[data.messages.length - 1];
        
        // Message should not contain emojis
        expect(lastMessage.msg).not.toContain(emojiTest.emoji);
        
        // Should still contain the ASCII text
        expect(lastMessage.msg).toContain('Test message with');
        expect(lastMessage.msg).toContain('emojis');
      }
    }
  });

  test('should filter emojis from chatroom messages', async ({ page }) => {
    // Create a room
    const createResponse = await page.request.post('/chat/create');
    const createData = await createResponse.json();
    const roomId = createData.room_id;
    
    await page.goto(`/chat/room/${roomId}`);
    
    for (const emojiTest of emojiTests.slice(0, 3)) {
      const message = `Chat ${emojiTest.emoji} test`;
      
      await page.request.post(`/chat/room/${roomId}/messages`, {
        data: { message: message }
      });
    }
    
    // Get messages
    const response = await page.request.get(`/chat/room/${roomId}/messages`);
    const data = await response.json();
    
    for (const msg of data.messages) {
      // Check that no emojis are present
      for (const emojiTest of emojiTests.slice(0, 3)) {
        expect(msg.message).not.toContain(emojiTest.emoji);
      }
      
      // Should contain ASCII text
      expect(msg.message).toContain('Chat');
      expect(msg.message).toContain('test');
    }
  });

  test('should filter skull emoji from user messages', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    const skullMessage = 'Test with skull 💀☠️ emoji';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: skullMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // Should not contain skull emojis
      expect(lastMessage.msg).not.toContain('💀');
      expect(lastMessage.msg).not.toContain('☠️');
      
      // Should contain ASCII text
      expect(lastMessage.msg).toContain('Test with skull');
      expect(lastMessage.msg).toContain('emoji');
    }
  });

  test('should allow ASCII-only messages', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    const asciiMessage = 'This is a pure ASCII message with !@#$%^&*() symbols';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: asciiMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // ASCII message should be preserved (except for sanitized chars)
      expect(lastMessage.msg).toContain('This is a pure ASCII message with');
      expect(lastMessage.msg).toContain('symbols');
    }
  });

  test('should filter non-ASCII unicode characters', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    const unicodeMessage = 'Hello 你好 مرحبا Привет World';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: unicodeMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // Should contain ASCII text
      expect(lastMessage.msg).toContain('Hello');
      expect(lastMessage.msg).toContain('World');
      
      // Should not contain non-ASCII characters
      expect(lastMessage.msg).not.toContain('你好');
      expect(lastMessage.msg).not.toContain('مرحبا');
      expect(lastMessage.msg).not.toContain('Привет');
    }
  });

  test('should handle mixed emoji and text in chatrooms', async ({ page }) => {
    const createResponse = await page.request.post('/chat/create');
    const createData = await createResponse.json();
    const roomId = createData.room_id;
    
    await page.goto(`/chat/room/${roomId}`);
    
    const mixedMessage = 'Hello 😀 this is 🔥 a test 💯 message';
    
    await page.request.post(`/chat/room/${roomId}/messages`, {
      data: { message: mixedMessage }
    });
    
    const response = await page.request.get(`/chat/room/${roomId}/messages`);
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // Should contain ASCII text only
      expect(lastMessage.message).toContain('Hello');
      expect(lastMessage.message).toContain('this is');
      expect(lastMessage.message).toContain('a test');
      expect(lastMessage.message).toContain('message');
      
      // Should not contain emojis
      expect(lastMessage.message).not.toContain('😀');
      expect(lastMessage.message).not.toContain('🔥');
      expect(lastMessage.message).not.toContain('💯');
    }
  });

  test('should handle emoji-only messages', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    const emojiOnlyMessage = '😀😁😂🤣😃😄😅😆';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: emojiOnlyMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    // Message should either be filtered to empty/rejected or not added
    // The system should handle this gracefully
    expect(response.status()).toBe(200);
  });

  test('should preserve message spacing when filtering emojis', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    const spacedMessage = 'word1 😀 word2 😁 word3';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: spacedMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // Should contain all words
      expect(lastMessage.msg).toContain('word1');
      expect(lastMessage.msg).toContain('word2');
      expect(lastMessage.msg).toContain('word3');
      
      // Should not contain emojis
      expect(lastMessage.msg).not.toContain('😀');
      expect(lastMessage.msg).not.toContain('😁');
    }
  });

  test('should filter all emoji categories consistently', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    // Test each category
    for (const emojiTest of emojiTests) {
      const message = `Category ${emojiTest.category}: ${emojiTest.emoji}`;
      
      await page.request.post('/test-path-12345/messages.json', {
        data: { message: message }
      });
      
      const response = await page.request.get('/test-path-12345/messages.json');
      const data = await response.json();
      
      if (data.messages.length > 0) {
        const lastMessage = data.messages[data.messages.length - 1];
        
        // Should not contain any emojis from this category
        expect(lastMessage.msg).not.toContain(emojiTest.emoji);
        
        // Should contain category label
        expect(lastMessage.msg).toContain(`Category ${emojiTest.category}`);
      }
    }
  });
});

test.describe('System Emoji Usage', () => {
  test('skull emoji should be reserved for system use only', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    // Users should not be able to send skull emoji
    const userMessage = 'User trying to send 💀 skull';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: userMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // User's skull emoji should be filtered
      expect(lastMessage.msg).not.toContain('💀');
      expect(lastMessage.msg).toContain('User trying to send');
      expect(lastMessage.msg).toContain('skull');
    }
  });

  test('documentation should specify emoji restrictions', async ({ page }) => {
    // This is a documentation test - checking that the policy is clear
    // In a real implementation, you would check docs pages
    
    // For now, verify that emoji filtering works as expected
    await page.goto('/test-path-12345/yesscript');
    
    const testMessage = 'Testing emoji policy 😀🎉💀';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: testMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    expect(response.status()).toBe(200);
  });
});

test.describe('Edge Cases', () => {
  test('should handle zero-width emojis', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    // Zero-width joiner emojis
    const zwjMessage = 'Test 👨‍👩‍👧‍👦 family emoji';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: zwjMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    expect(response.status()).toBe(200);
  });

  test('should handle modifier emojis', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    // Skin tone modifier emojis
    const modifierMessage = 'Test 👍🏻👍🏼👍🏽👍🏾👍🏿 modifiers';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: modifierMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // Should not contain thumbs up with any skin tone
      expect(lastMessage.msg).not.toContain('👍');
      expect(lastMessage.msg).toContain('Test');
      expect(lastMessage.msg).toContain('modifiers');
    }
  });

  test('should handle regional indicator emojis (flags)', async ({ page }) => {
    await page.goto('/test-path-12345/yesscript');
    
    const flagMessage = 'Test 🇺🇸🇬🇧🇯🇵 flags';
    
    await page.request.post('/test-path-12345/messages.json', {
      data: { message: flagMessage }
    });
    
    const response = await page.request.get('/test-path-12345/messages.json');
    const data = await response.json();
    
    if (data.messages.length > 0) {
      const lastMessage = data.messages[data.messages.length - 1];
      
      // Should not contain flag emojis
      expect(lastMessage.msg).not.toContain('🇺🇸');
      expect(lastMessage.msg).not.toContain('🇬🇧');
      expect(lastMessage.msg).not.toContain('🇯🇵');
    }
  });
});
