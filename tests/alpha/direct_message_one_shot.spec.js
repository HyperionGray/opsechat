// @ts-check
/**
 * One-shot direct messages used to share a room id out of band.
 *
 * Default expiry is 60 s. The expiry behaviour is gated behind
 * RUN_SLOW_TESTS=1 so CI can finish in a reasonable time.
 */
const { test, expect } = require('@playwright/test');

test.describe('Direct message share-room flow', () => {
  test('sends a DM and the recipient can fetch the room id once', async ({ request }) => {
    const create = await request.post('/chat/create');
    expect(create.status()).toBe(200);
    const roomId = (await create.json()).room_id;

    const send = await request.post('/chat/dm/send', {
      data: { room_id: roomId, message: 'meet you here' },
    });
    expect(send.status()).toBe(200);
    const body = await send.json();
    expect(body.success).toBe(true);
    expect(typeof body.dm_id).toBe('string');
    expect(body.expires_in).toBe(60);

    const view = await request.get(body.dm_url);
    expect(view.status()).toBe(200);
    const dm = await view.json();
    expect(dm.room_id).toBe(roomId);
    expect(dm.message).toBe('meet you here');
    expect(dm.expires_in).toBeLessThanOrEqual(60);
  });

  test('rejects an empty message', async ({ request }) => {
    const create = await request.post('/chat/create');
    const roomId = (await create.json()).room_id;
    const response = await request.post('/chat/dm/send', {
      data: { room_id: roomId, message: '' },
    });
    expect(response.status()).toBe(400);
  });

  test('rejects a too-long message', async ({ request }) => {
    const create = await request.post('/chat/create');
    const roomId = (await create.json()).room_id;
    const tooLong = 'x'.repeat(201);
    const response = await request.post('/chat/dm/send', {
      data: { room_id: roomId, message: tooLong },
    });
    expect(response.status()).toBe(400);
  });

  test.describe('expiry behaviour (slow)', () => {
    test.skip(!process.env.RUN_SLOW_TESTS, 'set RUN_SLOW_TESTS=1 to enable');

    test('DM is gone after 65 seconds', async ({ request }) => {
      test.setTimeout(120_000);
      const create = await request.post('/chat/create');
      const roomId = (await create.json()).room_id;
      const send = await request.post('/chat/dm/send', {
        data: { room_id: roomId, message: 'short-lived' },
      });
      const dmUrl = (await send.json()).dm_url;

      // Wait past the 60 s expiry plus the 30 s cleanup tick (~70-95 s total
      // worst case). Cleanup loop runs every 30 s; first poll after 65 s may
      // return 200 if the cleanup tick hasn't fired yet, so we retry once.
      await new Promise((r) => setTimeout(r, 65_000));
      let response = await request.get(dmUrl);
      if (response.status() === 200) {
        await new Promise((r) => setTimeout(r, 35_000));
        response = await request.get(dmUrl);
      }
      expect(response.status()).toBe(404);
    });
  });
});
