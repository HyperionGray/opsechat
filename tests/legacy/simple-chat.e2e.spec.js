/**
 * Simple Chat Rooms E2E Tests
 *
 * Covers the closed-roster OpenPGP room shell and bootstrap UI.
 */

const { test, expect } = require('@playwright/test');

const randomIdentityAdjectives = [
  'Swift', 'Silent', 'Dark', 'Ghost', 'Shadow', 'Phantom',
  'Cipher', 'Echo', 'Rogue', 'Viper', 'Stealth', 'Void',
];

const randomIdentityNouns = [
  'Raven', 'Wolf', 'Fox', 'Hawk', 'Lynx', 'Owl',
  'Cobra', 'Tiger', 'Falcon', 'Spider', 'Serpent', 'Dragon',
];

const randomIdentityDisplayPattern = new RegExp(
  `^(${randomIdentityAdjectives.join('|')}) (${randomIdentityNouns.join('|')}) \\d{4}$`
);

const randomIdentityMemberIdPattern = new RegExp(
  `^(${randomIdentityAdjectives.map((value) => value.toLowerCase()).join('|')})-` +
  `(${randomIdentityNouns.map((value) => value.toLowerCase()).join('|')})-\\d{4}$`
);

test.describe('Simple Chat Room Tests', () => {
  let baseURL;

  test.beforeAll(async () => {
    baseURL = process.env.TEST_URL || 'http://localhost:5001';
  });

  test('should load chat index page', async ({ page }) => {
    await page.goto(`${baseURL}/chat`);
    await expect(page.locator('h1')).toContainText('OpSecChat');
    await expect(page.locator('#createRoomBtn')).toBeVisible();
    await expect(page.getByText('Closed-roster OpenPGP room bootstrap')).toBeVisible();
  });

  test('should create a new chat room and render bootstrap UI', async ({ page }) => {
    await page.goto(`${baseURL}/chat`);
    await page.locator('#createRoomBtn').click();
    await page.waitForURL(/\/chat\/room\/[\w-]+/, { timeout: 5000 });

    await expect(page.locator('h1')).toContainText('Closed-Roster OpSecChat');
    await expect(page.locator('#memberIdInput')).toBeVisible();
    await expect(page.locator('#memberIdInput')).toHaveValue(randomIdentityMemberIdPattern);
    await expect(page.locator('#displayNameInput')).toHaveValue(randomIdentityDisplayPattern);
    await expect(page.locator('#privateKeyInput')).toBeVisible();
    await expect(page.locator('#peerPublicKeyInput')).toBeVisible();
    await expect(page.locator('#lockRosterBtn')).toBeVisible();
    await expect(page.locator('#sendBtn')).toBeDisabled();
  });

  test('should acknowledge the security warning', async ({ page }) => {
    await page.goto(`${baseURL}/chat`);
    await page.locator('#createRoomBtn').click();
    await page.waitForURL(/\/chat\/room\/[\w-]+/, { timeout: 5000 });

    const warning = page.locator('#securityWarning');
    await expect(warning).toBeVisible();
    await page.locator('#acceptSecurityWarningBtn').click();
    await expect(warning).toBeHidden();
  });

  test('message input should use the backend max length', async ({ page }) => {
    await page.goto(`${baseURL}/chat`);
    await page.locator('#createRoomBtn').click();
    await page.waitForURL(/\/chat\/room\/[\w-]+/, { timeout: 5000 });

    const messageInput = page.locator('#messageInput');
    await expect(messageInput).toHaveAttribute('maxlength', '500');
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
  });

  test('should return closed-roster state via API', async ({ request }) => {
    const createResponse = await request.post(`${baseURL}/chat/create`);
    const createData = await createResponse.json();
    const roomId = createData.room_id;

    const stateResponse = await request.get(`${baseURL}/chat/room/${roomId}/state`);
    expect(stateResponse.ok()).toBeTruthy();

    const stateData = await stateResponse.json();
    expect(stateData).toHaveProperty('mode', 'closed_roster_openpgp_v1');
    expect(stateData).toHaveProperty('active_epoch', null);
  });

  test('should deprecate the shared-key endpoint', async ({ request }) => {
    const createResponse = await request.post(`${baseURL}/chat/create`);
    const createData = await createResponse.json();
    const roomId = createData.room_id;

    const keyResponse = await request.get(`${baseURL}/chat/room/${roomId}/key`);
    expect(keyResponse.status()).toBe(410);
  });
});
