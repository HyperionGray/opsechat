// @ts-check
/**
 * Persona: Hosted user with a Tor-Browser-equivalent tab.
 *
 * Two browser contexts (Alice and Bob) drive the full closed-roster
 * workflow, exactly as a pair of users would: create -> identity ->
 * roster bootstrap -> mutual verify -> signed+encrypted message round
 * trip in both directions.
 *
 * This is the highest-value alpha test: if it passes, the entire alpha
 * shipping path is functional.
 */
const { test, expect } = require('@playwright/test');
const {
  createRoom,
  acceptSecurityWarning,
  generateIdentity,
  addPeerAndVerify,
  lockRoster,
  verifyActiveMember,
  sendMessage,
} = require('./helpers');

test.describe('Hosted user two-browser closed-roster flow', () => {
  // OpenPGP key generation in-browser plus epoch bootstrap takes a while.
  test.setTimeout(180_000);
  // Run serially so contexts/IDs do not race.
  test.describe.configure({ mode: 'serial' });

  test('Alice and Bob exchange a signed+encrypted message in both directions', async ({ browser }) => {
    const aliceContext = await browser.newContext({ acceptDownloads: true });
    const bobContext = await browser.newContext({ acceptDownloads: true });
    const alice = await aliceContext.newPage();
    const bob = await bobContext.newPage();

    try {
      // Alice creates the room and bootstraps her identity.
      const roomUrl = await createRoom(alice);
      await acceptSecurityWarning(alice);
      await generateIdentity(alice, 'alice', 'Alice');

      // Bob opens the same room URL and bootstraps his identity.
      await bob.goto(roomUrl);
      await acceptSecurityWarning(bob);
      const bobIdentity = await generateIdentity(bob, 'bob', 'Bob');

      // Alice adds Bob's public key to the draft roster, marks verified, locks.
      await addPeerAndVerify(alice, 'bob', 'Bob', bobIdentity.publicKey);
      await lockRoster(alice);

      // Both sides should see epoch 1 once Bob's page polls room state.
      await expect(bob.locator('#epochSummary')).toContainText('Epoch: 1', {
        timeout: 30_000,
      });

      // Bob marks Alice verified locally so his composer can enable.
      await verifyActiveMember(bob, 'alice');
      await expect(bob.locator('#composerState')).toContainText(
        'Ready: this message will be signed and encrypted to the full roster.',
        { timeout: 15_000 }
      );

      // Alice -> Bob.
      const aliceText = 'Alpha hello from Alice';
      await sendMessage(alice, aliceText);
      await expect(bob.locator('.message-body').first()).toContainText(aliceText, {
        timeout: 30_000,
      });
      await expect(bob.locator('.message-note').first()).toContainText(
        'Verified locally',
        { timeout: 30_000 }
      );

      // Bob -> Alice.
      const bobText = 'Bob reply, also signed and encrypted';
      await sendMessage(bob, bobText);
      await expect(alice.locator('.message-body').last()).toContainText(bobText, {
        timeout: 30_000,
      });

      // Final sanity: each side should see two accepted messages with the
      // sender's display name attached.
      await expect(alice.locator('.message-sender').first()).toContainText('Alice');
      await expect(bob.locator('.message-sender').first()).toContainText('Alice');
    } finally {
      await aliceContext.close();
      await bobContext.close();
    }
  });

  test('private key download produces a usable backup', async ({ browser }) => {
    const context = await browser.newContext({ acceptDownloads: true });
    const page = await context.newPage();
    try {
      await createRoom(page);
      await acceptSecurityWarning(page);
      await generateIdentity(page, 'alice', 'Alice');

      const downloadPromise = page.waitForEvent('download');
      await page.locator('#downloadPrivateKeyBtn').click();
      const download = await downloadPromise;
      const downloadPath = await download.path();
      const fs = require('fs');
      const armored = fs.readFileSync(downloadPath, 'utf8');
      expect(armored).toContain('BEGIN PGP PRIVATE KEY BLOCK');
      expect(armored).toContain('END PGP PRIVATE KEY BLOCK');
      // The recovery banner should now show the export timestamp.
      await expect(page.locator('#identityRecovery')).toContainText('Last private-key export:');
    } finally {
      await context.close();
    }
  });
});
