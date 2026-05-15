// @ts-check
/**
 * Persona: Self-hosted ad-hoc user.
 *
 * The user just ran `python bin/chat-room.py` (or `--tor`) on their own
 * machine. The same Flask app is exposed at the configured base URL.
 *
 * What this spec proves:
 * - The operator console renders at `/`.
 * - The chat index renders at `/chat`.
 * - "Create New Chat Room" actually creates a room and lands the browser on
 *   `/chat/room/<id>` with the closed-roster UI shell ready for bootstrap.
 * - The composer is correctly disabled until the roster is locked.
 * - `/health` reports a healthy status.
 *
 * Driven against the real Flask app (see `tests/real_app_server.py`).
 */
const { test, expect } = require('@playwright/test');
const { createRoom } = require('./helpers');

test.describe('Self-hosted ad-hoc persona', () => {
  test('operator console renders with core profile', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Operator Console' })).toBeVisible();
    await expect(page.getByText('Deployment profile')).toBeVisible();
    // Profile string lives in a <dd> next to the "Deployment profile" <dt>.
    const profileDd = page.locator('dt:has-text("Deployment profile") + dd');
    await expect(profileDd).toContainText('core');
  });

  test('chat index renders with the create-room button', async ({ page }) => {
    await page.goto('/chat');
    // Hero pattern from the operator console: an eyebrow with the brand,
    // then the section H1.
    await expect(page.locator('.eyebrow')).toContainText('OpSecChat');
    await expect(page.locator('h1')).toContainText('Secure Chat Rooms');
    await expect(page.locator('#createRoomBtn')).toBeVisible();
    // No emoji glyphs should be on the alpha-shipping landing page.
    const html = await page.content();
    // U+26A1 high voltage and U+26A0 warning sign were the previous offenders.
    expect(html).not.toMatch(/[\u26A0\u26A1\u{1F300}-\u{1FAFF}]/u);
  });

  test('creating a room lands on the room shell with composer disabled', async ({ page }) => {
    await createRoom(page);
    await expect(page.locator('h1')).toContainText('Closed-Roster OpSecChat');
    await expect(page.locator('#memberIdInput')).toBeVisible();
    await expect(page.locator('#privateKeyInput')).toBeVisible();
    await expect(page.locator('#peerPublicKeyInput')).toBeVisible();
    await expect(page.locator('#lockRosterBtn')).toBeVisible();
    // Composer must stay disabled until the roster is locked + identities set.
    await expect(page.locator('#sendBtn')).toBeDisabled();
    await expect(page.locator('#composerState')).toContainText(/Bootstrap|Acknowledge/);
  });

  test('/health returns a healthy JSON payload', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('application/json');
    const body = await response.json();
    expect(body.status).toBe('healthy');
    expect(typeof body.version).toBe('string');
    expect(body.version.length).toBeGreaterThan(0);
  });

  test('a missing room id renders a friendly error page', async ({ page }) => {
    const response = await page.goto('/chat/room/this-room-id-does-not-exist');
    expect(response && response.status()).toBe(404);
    await expect(page.locator('h1')).toContainText('Error');
    await expect(page.locator('a[href="/chat"]')).toBeVisible();
  });
});
