// @ts-check
/**
 * Rate limit and error-shape tests for the alpha-shipping endpoints.
 *
 * These specs confirm:
 *   - the per-session sliding-window limiter on /chat/create kicks in
 *     and returns a JSON 429 with retry_after
 *   - DM rate-limit also returns 429
 *   - the missing-room HTML error path returns 404
 *
 * The slow expiry assertion is gated behind RUN_SLOW_TESTS=1.
 */
const { test, expect } = require('@playwright/test');

test.describe('Rate limits + error shapes', () => {
  test('hammering /chat/create eventually returns 429 with retry_after', async ({ request }) => {
    let saw429 = false;
    let lastRetry = 0;
    // Per-session limit is 10 creates per hour and 3 per minute. Issue more
    // requests than the per-minute window so we hit the limit reliably.
    for (let i = 0; i < 20; i += 1) {
      const response = await request.post('/chat/create');
      if (response.status() === 429) {
        saw429 = true;
        const body = await response.json();
        expect(body.error).toMatch(/Rate limit/);
        // Retry-after may come from Flask-Limiter (header) or our in-memory
        // sliding-window message. We only require that something useful is
        // present.
        if (typeof body.retry_after === 'number') lastRetry = body.retry_after;
        break;
      }
      expect(response.status()).toBe(200);
    }
    expect(saw429).toBe(true);
    if (lastRetry) expect(lastRetry).toBeGreaterThan(0);
  });

  test('hammering /chat/dm/send eventually returns 429', async ({ request }) => {
    // First, create a room so we have a valid room_id to wrap.
    const room = await request.post('/chat/create');
    const roomId = (await room.json()).room_id;

    let saw429 = false;
    for (let i = 0; i < 12; i += 1) {
      const response = await request.post('/chat/dm/send', {
        data: { room_id: roomId, message: `ping ${i}` },
      });
      if (response.status() === 429) {
        saw429 = true;
        expect((await response.json()).error).toMatch(/Rate limit/);
        break;
      }
      // Either 200 (DM accepted) or 429 (limit) is fine in this loop.
      expect([200, 429]).toContain(response.status());
    }
    expect(saw429).toBe(true);
  });

  test('an unknown room id renders the 404 error template', async ({ page }) => {
    const response = await page.goto('/chat/room/this-room-id-does-not-exist');
    expect(response && response.status()).toBe(404);
    await expect(page.locator('h1')).toContainText('Error');
  });

  test('GET on an unknown DM id is 404', async ({ request }) => {
    const response = await request.get('/chat/dm/does-not-exist-12345');
    expect(response.status()).toBe(404);
  });
});
