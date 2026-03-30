/**
 * Simple Chat Rooms E2E Tests
 * 
 * Tests the new simplified chat room functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Simple Chat Room Tests', () => {
  let baseURL;
  
  test.beforeAll(async () => {
    // Assuming server is running on localhost:5001 in test mode
    baseURL = process.env.TEST_URL || 'http://localhost:5001';
  });

  test('should load chat index page', async ({ page }) => {
    await page.goto(`${baseURL}/chat`);
    
    // Check for main heading
    await expect(page.locator('h1')).toContainText('OpSecChat');
    
    // Check for create button
    const createBtn = page.locator('#createRoomBtn');
    await expect(createBtn).toBeVisible();
  });

  test('should create a new chat room', async ({ page }) => {
    await page.goto(`${baseURL}/chat`);
    
    // Click create room button
    const createBtn = page.locator('#createRoomBtn');
    await createBtn.click();
    
    // Wait for redirect to room page
    await page.waitForURL(/\/chat\/room\/[a-zA-Z0-9_-]+/, { timeout: 5000 });
    
    // Check we're on a room page
    const url = page.url();
    expect(url).toMatch(/\/chat\/room\/[a-zA-Z0-9_-]+/);
    
    // Check room elements are present
    await expect(page.locator('h1')).toContainText('OpSecChat Room');
    await expect(page.locator('#messageInput')).toBeVisible();
    await expect(page.locator('#sendBtn')).toBeVisible();
  });

  test('should send and receive messages in a room', async ({ page }) => {
    // Create a room
    await page.goto(`${baseURL}/chat`);
    const createBtn = page.locator('#createRoomBtn');
    await createBtn.click();
    await page.waitForURL(/\/chat\/room\/[a-zA-Z0-9_-]+/, { timeout: 5000 });
    
    // Send a message
    const messageInput = page.locator('#messageInput');
    const sendBtn = page.locator('#sendBtn');
    
    await messageInput.fill('Test message from Playwright');
    await sendBtn.click();
    
    // Wait for message to appear
    await page.waitForTimeout(1000);
    
    // Check message is displayed
    const messagesContainer = page.locator('#messagesContainer');
    await expect(messagesContainer).toContainText('Test message from Playwright');
  });

  test('should show username with color', async ({ page }) => {
    // Create a room
    await page.goto(`${baseURL}/chat`);
    const createBtn = page.locator('#createRoomBtn');
    await createBtn.click();
    await page.waitForURL(/\/chat\/room\/[a-zA-Z0-9_-]+/, { timeout: 5000 });
    
    // Check username is displayed in header
    const userInfo = page.locator('#userInfo');
    await expect(userInfo).toContainText('You are:');
    
    // Username should match pattern: Adjective+Noun+Number
    const usernameSpan = userInfo.locator('span');
    const usernameText = await usernameSpan.textContent();
    expect(usernameText).toMatch(/^[A-Z][a-z]+[A-Z][a-z]+\d{4}$/);
  });

  test('should toggle encryption', async ({ page }) => {
    // Create a room
    await page.goto(`${baseURL}/chat`);
    const createBtn = page.locator('#createRoomBtn');
    await createBtn.click();
    await page.waitForURL(/\/chat\/room\/[a-zA-Z0-9_-]+/, { timeout: 5000 });
    
    // Check encryption toggle
    const encryptionToggle = page.locator('#encryptionToggle');
    await expect(encryptionToggle).toBeVisible();
    
    // Initially should be off
    const encryptionStatus = page.locator('#encryptionStatus');
    await expect(encryptionStatus).toContainText('OFF');
    
    // Toggle encryption on
    await encryptionToggle.check();
    await page.waitForTimeout(500);
    
    // Should now be on
    await expect(encryptionStatus).toContainText('ON');
  });

  test('should track user count', async ({ page }) => {
    // Create a room
    await page.goto(`${baseURL}/chat`);
    const createBtn = page.locator('#createRoomBtn');
    await createBtn.click();
    await page.waitForURL(/\/chat\/room\/[a-zA-Z0-9_-]+/, { timeout: 5000 });
    
    // Check user count is displayed
    const userCount = page.locator('#userCount');
    await expect(userCount).toContainText('Users:');
    
    // Should show at least 1 user (us)
    const countText = await userCount.textContent();
    expect(countText).toMatch(/Users: \d+/);
  });

  test('should handle message sanitization', async ({ page }) => {
    // Create a room
    await page.goto(`${baseURL}/chat`);
    const createBtn = page.locator('#createRoomBtn');
    await createBtn.click();
    await page.waitForURL(/\/chat\/room\/[a-zA-Z0-9_-]+/, { timeout: 5000 });
    
    // Try to send a message with HTML/special chars
    const messageInput = page.locator('#messageInput');
    const sendBtn = page.locator('#sendBtn');
    
    await messageInput.fill('<script>alert("XSS")</script>');
    await sendBtn.click();
    
    await page.waitForTimeout(1000);
    
    // Message should be sanitized (no angle brackets)
    const messagesContainer = page.locator('#messagesContainer');
    const text = await messagesContainer.textContent();
    expect(text).not.toContain('<script>');
    expect(text).not.toContain('</script>');
  });

  test('should respect max message length', async ({ page }) => {
    // Create a room
    await page.goto(`${baseURL}/chat`);
    const createBtn = page.locator('#createRoomBtn');
    await createBtn.click();
    await page.waitForURL(/\/chat\/room\/[a-zA-Z0-9_-]+/, { timeout: 5000 });
    
    // Check input has maxlength attribute
    const messageInput = page.locator('#messageInput');
    const maxLength = await messageInput.getAttribute('maxlength');
    expect(maxLength).toBe('500');
  });

});

test.describe('Simple Chat API Tests', () => {
  let baseURL;
  
  test.beforeAll(async () => {
    baseURL = process.env.TEST_URL || 'http://localhost:5001';
  });

  test('should create room via API', async ({ request }) => {
    const response = await request.post(`${baseURL}/chat/create`);
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data).toHaveProperty('success', true);
    expect(data).toHaveProperty('room_id');
    expect(data).toHaveProperty('room_url');
    expect(data.room_id).toMatch(/^[a-zA-Z0-9_-]+$/);
  });

  test('should post message via API', async ({ request }) => {
    // Create a room first
    const createResponse = await request.post(`${baseURL}/chat/create`);
    const createData = await createResponse.json();
    const roomId = createData.room_id;
    
    // Post a message
    const messageResponse = await request.post(
      `${baseURL}/chat/room/${roomId}/messages`,
      {
        data: { message: 'Test API message' }
      }
    );
    
    expect(messageResponse.ok()).toBeTruthy();
    const messageData = await messageResponse.json();
    expect(messageData).toHaveProperty('success', true);
  });

  test('should get messages via API', async ({ request }) => {
    // Create a room and post a message
    const createResponse = await request.post(`${baseURL}/chat/create`);
    const createData = await createResponse.json();
    const roomId = createData.room_id;
    
    await request.post(
      `${baseURL}/chat/room/${roomId}/messages`,
      {
        data: { message: 'Test message for retrieval' }
      }
    );
    
    // Get messages
    const getResponse = await request.get(
      `${baseURL}/chat/room/${roomId}/messages`
    );
    
    expect(getResponse.ok()).toBeTruthy();
    const getData = await getResponse.json();
    
    expect(getData).toHaveProperty('messages');
    expect(getData).toHaveProperty('user_count');
    expect(getData.messages).toBeInstanceOf(Array);
    expect(getData.messages.length).toBeGreaterThan(0);
    expect(getData.messages[0]).toHaveProperty('username');
    expect(getData.messages[0]).toHaveProperty('message');
    expect(getData.messages[0]).toHaveProperty('color');
  });

  test('should return 404 for non-existent room', async ({ request }) => {
    const response = await request.get(
      `${baseURL}/chat/room/nonexistentroom123/messages`
    );
    
    expect(response.status()).toBe(404);
  });
});
