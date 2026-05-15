// @ts-check
/**
 * Server-side validation contract for the closed-roster OpenPGP room API.
 *
 * Every error path here protects against a real way the room could be
 * weakened: missing roster, mismatched epoch, sender outside the roster,
 * recipient set drifting from the roster, anonymous recipients, and the
 * deprecated shared-key endpoint.
 *
 * Driven via Playwright's request fixture (no browser needed).
 */
const { test, expect } = require('@playwright/test');
const crypto = require('crypto');

const ENVELOPE_TYPE = 'closed_roster_openpgp_v1';

function fp(seed) {
  return crypto.createHash('sha256').update(`${seed}`).digest('hex').toUpperCase();
}
function keyId(seed) {
  return fp(seed).slice(0, 16);
}
function memberRecord(memberId) {
  return {
    member_id: memberId,
    display_name: memberId.charAt(0).toUpperCase() + memberId.slice(1),
    signing_fingerprint: fp(`${memberId}-sign`),
    encryption_fingerprint: fp(`${memberId}-enc`),
    signing_key_id: keyId(`${memberId}-sign-key`),
    encryption_key_id: keyId(`${memberId}-enc-key`),
    public_key_armored:
      `-----BEGIN PGP PUBLIC KEY BLOCK-----\n${memberId}\n-----END PGP PUBLIC KEY BLOCK-----`,
  };
}
function fingerprintsOf(roster) {
  return roster.map((m) => m.encryption_fingerprint);
}
function keyIdsOf(roster) {
  return roster.map((m) => m.encryption_key_id);
}

async function createRoom(request) {
  const response = await request.post('/chat/create');
  expect(response.status()).toBe(200);
  return (await response.json()).room_id;
}

async function bootstrap(request, roomId, members, creator = 'alice') {
  return request.post(`/chat/room/${roomId}/state/bootstrap`, {
    data: { creator_member_id: creator, members },
  });
}

function envelopeFor(roomId, roster, sender, overrides = {}) {
  const fps = fingerprintsOf(roster);
  const keys = keyIdsOf(roster);
  return {
    envelope_type: ENVELOPE_TYPE,
    room_id: roomId,
    epoch: 1,
    sender_member_id: sender.member_id,
    sender_signing_fingerprint: sender.signing_fingerprint,
    roster_hash: 'placeholder',
    recipient_encryption_fingerprints: fps,
    intended_recipient_fingerprints: fps,
    recipient_encryption_key_ids: keys,
    armored_message:
      '-----BEGIN PGP MESSAGE-----\nopaque\n-----END PGP MESSAGE-----',
    ...overrides,
  };
}

async function bootstrapAndGetRosterHash(request, roomId, roster) {
  const response = await bootstrap(request, roomId, roster);
  expect(response.status()).toBe(200);
  return (await response.json()).active_epoch.roster_hash;
}

test.describe('Closed-roster server validation', () => {
  test('GET /chat/room/<id>/key returns 410 with deprecation pointer', async ({ request }) => {
    const roomId = await createRoom(request);
    const response = await request.get(`/chat/room/${roomId}/key`);
    expect(response.status()).toBe(410);
    const body = await response.json();
    expect(body.deprecated).toBe(true);
    expect(body.replacement).toBe(`/chat/room/${roomId}/state`);
  });

  test('messages POST before bootstrap is rejected with 409', async ({ request }) => {
    const roomId = await createRoom(request);
    const response = await request.post(`/chat/room/${roomId}/messages`, {
      data: { message: 'plaintext should never work' },
    });
    expect(response.status()).toBe(409);
    expect((await response.json()).error).toMatch(/Bootstrap|not initialized/);
  });

  test('bootstrap with no members returns 400', async ({ request }) => {
    const roomId = await createRoom(request);
    const response = await bootstrap(request, roomId, []);
    expect(response.status()).toBe(400);
  });

  test('bootstrap with duplicate signing key id is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const alice = memberRecord('alice');
    const bob = memberRecord('bob');
    bob.signing_key_id = alice.signing_key_id;
    const response = await bootstrap(request, roomId, [alice, bob]);
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toMatch(/signing key ids must be unique/);
  });

  test('bootstrap a second time on the same room is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const roster = [memberRecord('alice'), memberRecord('bob')];
    expect((await bootstrap(request, roomId, roster)).status()).toBe(200);
    const second = await bootstrap(request, roomId, [memberRecord('alice'), memberRecord('carol')]);
    expect(second.status()).toBe(400);
    expect((await second.json()).error).toMatch(/already initialized/);
  });

  test('message envelope with mismatched room_id is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const roster = [memberRecord('alice'), memberRecord('bob')];
    const rosterHash = await bootstrapAndGetRosterHash(request, roomId, roster);
    const envelope = envelopeFor(roomId, roster, roster[0], {
      room_id: 'a-different-room-id',
      roster_hash: rosterHash,
    });
    const response = await request.post(`/chat/room/${roomId}/messages`, { data: envelope });
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toMatch(/room_id mismatch/);
  });

  test('message envelope with mismatched epoch is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const roster = [memberRecord('alice'), memberRecord('bob')];
    const rosterHash = await bootstrapAndGetRosterHash(request, roomId, roster);
    const envelope = envelopeFor(roomId, roster, roster[0], {
      epoch: 99,
      roster_hash: rosterHash,
    });
    const response = await request.post(`/chat/room/${roomId}/messages`, { data: envelope });
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toMatch(/epoch mismatch/);
  });

  test('message from a sender outside the roster is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const roster = [memberRecord('alice'), memberRecord('bob')];
    const rosterHash = await bootstrapAndGetRosterHash(request, roomId, roster);
    const stranger = memberRecord('mallory');
    const envelope = envelopeFor(roomId, roster, stranger, { roster_hash: rosterHash });
    const response = await request.post(`/chat/room/${roomId}/messages`, { data: envelope });
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toMatch(/not part of the room roster/);
  });

  test('mismatched roster hash is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const roster = [memberRecord('alice'), memberRecord('bob')];
    await bootstrapAndGetRosterHash(request, roomId, roster);
    const envelope = envelopeFor(roomId, roster, roster[0], {
      roster_hash: 'A'.repeat(64),
    });
    const response = await request.post(`/chat/room/${roomId}/messages`, { data: envelope });
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toMatch(/roster hash mismatch/);
  });

  test('recipient set missing a roster member is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const roster = [memberRecord('alice'), memberRecord('bob')];
    const rosterHash = await bootstrapAndGetRosterHash(request, roomId, roster);
    const envelope = envelopeFor(roomId, roster, roster[0], {
      roster_hash: rosterHash,
      // Drop bob from the recipient set.
      recipient_encryption_fingerprints: [roster[0].encryption_fingerprint],
      recipient_encryption_key_ids: [roster[0].encryption_key_id],
    });
    const response = await request.post(`/chat/room/${roomId}/messages`, { data: envelope });
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toMatch(/recipient set does not match/);
  });

  test('explicit anonymous_recipients flag is rejected', async ({ request }) => {
    const roomId = await createRoom(request);
    const roster = [memberRecord('alice'), memberRecord('bob')];
    const rosterHash = await bootstrapAndGetRosterHash(request, roomId, roster);
    const envelope = envelopeFor(roomId, roster, roster[0], {
      roster_hash: rosterHash,
      anonymous_recipients: true,
    });
    const response = await request.post(`/chat/room/${roomId}/messages`, { data: envelope });
    expect(response.status()).toBe(400);
    expect((await response.json()).error).toMatch(/anonymous recipients are forbidden/);
  });
});
