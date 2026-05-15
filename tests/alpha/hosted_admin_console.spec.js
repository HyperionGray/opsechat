// @ts-check
/**
 * Persona: Operator hosting OpSecChat centrally.
 *
 * The operator hits the operator surfaces -- console, manifest, health,
 * version, chat stats -- and confirms the alpha profile keeps the email /
 * burner / HTTP mail surfaces intentionally hidden.
 */
const { test, expect } = require('@playwright/test');

test.describe('Hosted admin / operator', () => {
  test('console manifest reflects the core profile', async ({ request }) => {
    const response = await request.get('/console/api');
    expect(response.status()).toBe(200);
    const payload = await response.json();
    expect(payload.profile).toBe('core');
    expect(payload.extended_services_enabled).toBe(false);

    const serviceNames = payload.services.map((s) => s.name);
    expect(serviceNames).toContain('secure-chat');
    expect(serviceNames).toContain('health');
    // The extended-only services must NOT appear in the alpha manifest.
    expect(serviceNames).not.toContain('http-mail');
    expect(serviceNames).not.toContain('burner-receive');
  });

  test('health endpoint is JSON and reports active room count', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('status', 'healthy');
    expect(body).toHaveProperty('active_rooms');
    expect(typeof body.active_rooms).toBe('number');
    expect(body).toHaveProperty('uptime_seconds');
    expect(typeof body.uptime_seconds).toBe('number');
  });

  test('version endpoint returns service/version/timestamp', async ({ request }) => {
    const response = await request.get('/version');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.service).toBe('opsechat');
    expect(typeof body.version).toBe('string');
    expect(body.version.length).toBeGreaterThan(0);
    expect(typeof body.timestamp).toBe('string');
    // ISO 8601 with Z or offset.
    expect(body.timestamp).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });

  test('chat stats endpoint returns numeric counters', async ({ request }) => {
    const response = await request.get('/chat/stats');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(typeof body.active_rooms).toBe('number');
    expect(typeof body.active_users).toBe('number');
    expect(typeof body.total_messages).toBe('number');
    expect(typeof body.pending_dms).toBe('number');
    expect(body.config).toMatchObject({
      message_expiry_seconds: expect.any(Number),
      dm_expiry_seconds: expect.any(Number),
      room_inactive_seconds: expect.any(Number),
    });
  });

  test('responses set strict security headers', async ({ request }) => {
    const response = await request.get('/health');
    const headers = response.headers();
    expect(headers['content-security-policy']).toContain("default-src 'self'");
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['x-frame-options']).toBe('DENY');
    expect(headers['referrer-policy']).toBe('no-referrer');
  });

  test('console UI renders the manifest with no extended-only services', async ({ page }) => {
    await page.goto('/console');
    await expect(page.getByRole('heading', { name: 'Operator Console' })).toBeVisible();
    // The "Secure chat rooms" label appears as the card heading; assert there
    // is a card heading, then confirm the operational-health card too.
    await expect(page.getByRole('heading', { name: 'Secure chat rooms' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Operational health' })).toBeVisible();
    // Restricted services must not advertise themselves in the alpha console.
    await expect(page.getByRole('heading', { name: 'Restricted HTTP mail' })).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Restricted burner inboxes' })).toHaveCount(0);
  });
});
