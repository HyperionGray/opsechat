// @ts-check
/**
 * Headed slow-mo visual walkthrough.
 *
 * This spec only runs under the `chromium-headed-slowmo` project (see
 * playwright.config.js). It exists so a human can sit down, run
 *
 *   npm run test:alpha:slowmo
 *
 * and watch the entire alpha-shipping flow happen at human-readable speed,
 * with explicit narration in the console output.
 *
 * No new behaviour is exercised here -- everything is also covered by the
 * headless specs. Treat this as a canary for "does the docs walkthrough
 * still work end-to-end?"
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

function narrate(step, total, message) {
  // eslint-disable-next-line no-console
  console.log(`\n[step ${step}/${total}] ${message}`);
}

test.describe('Visual walkthrough (headed, slow-mo)', () => {
  test.setTimeout(240_000);

  test('walks the documented hosted-user flow end-to-end', async ({ browser }) => {
    const total = 9;
    const aliceContext = await browser.newContext({ acceptDownloads: true });
    const bobContext = await browser.newContext({ acceptDownloads: true });
    const alice = await aliceContext.newPage();
    const bob = await bobContext.newPage();

    try {
      narrate(1, total, 'Alice opens the chat index and creates a room.');
      const roomUrl = await createRoom(alice);
      await alice.waitForTimeout(1500);

      narrate(2, total, 'Alice acknowledges the security rules.');
      await acceptSecurityWarning(alice);
      await alice.waitForTimeout(1000);

      narrate(3, total, 'Alice generates her local OpenPGP identity.');
      await generateIdentity(alice, 'alice', 'Alice');
      await alice.waitForTimeout(1500);

      narrate(4, total, 'Bob opens the same room URL in a separate browser context.');
      await bob.goto(roomUrl);
      await acceptSecurityWarning(bob);
      await bob.waitForTimeout(1000);

      narrate(5, total, 'Bob generates his own identity.');
      const bobIdentity = await generateIdentity(bob, 'bob', 'Bob');
      await bob.waitForTimeout(1500);

      narrate(6, total, 'Alice adds Bob to the draft roster, marks verified, locks epoch 1.');
      await addPeerAndVerify(alice, 'bob', 'Bob', bobIdentity.publicKey);
      await alice.waitForTimeout(1000);
      await lockRoster(alice);
      await alice.waitForTimeout(1500);

      narrate(7, total, 'Bob sees the active roster and marks Alice verified.');
      await expect(bob.locator('#epochSummary')).toContainText('Epoch: 1', {
        timeout: 30_000,
      });
      await verifyActiveMember(bob, 'alice');
      await bob.waitForTimeout(1500);

      narrate(8, total, 'Alice sends a signed+encrypted message to the full roster.');
      await sendMessage(alice, 'Walkthrough hello from Alice');
      await expect(bob.locator('.message-body').first()).toContainText(
        'Walkthrough hello from Alice',
        { timeout: 30_000 }
      );
      await bob.waitForTimeout(2000);

      narrate(9, total, 'Bob replies; Alice receives the signed+encrypted message.');
      await sendMessage(bob, 'And a reply from Bob');
      await expect(alice.locator('.message-body').last()).toContainText(
        'And a reply from Bob',
        { timeout: 30_000 }
      );
      await alice.waitForTimeout(3000);
    } finally {
      await aliceContext.close();
      await bobContext.close();
    }
  });
});
