// @ts-check
/**
 * Shared helpers for OpSecChat alpha Playwright specs.
 *
 * These helpers drive the live UI exactly like a person would: they click
 * buttons, fill fields, and wait for visible state changes. They never
 * reach into Python state.
 */

const { expect } = require('@playwright/test');

/**
 * Create a new chat room from the index page and return the room URL.
 * @param {import('@playwright/test').Page} page
 */
async function createRoom(page) {
  await page.goto('/chat');
  await expect(page.locator('#createRoomBtn')).toBeVisible();
  await page.locator('#createRoomBtn').click();
  await page.waitForURL(/\/chat\/room\/[\w-]+/, { timeout: 15_000 });
  return page.url();
}

/**
 * Dismiss the modal closed-roster security warning if it is showing.
 * @param {import('@playwright/test').Page} page
 */
async function acceptSecurityWarning(page) {
  const warning = page.locator('#securityWarning');
  if (await warning.isVisible().catch(() => false)) {
    await page.locator('#acceptSecurityWarningBtn').click();
    await expect(warning).toBeHidden();
  }
}

/**
 * Fill the local-identity form and click "Generate Key Pair". Returns the
 * armored public and private key the page rendered.
 *
 * Key generation in OpenPGP.js takes ~5-15s on a cold worker.
 * @param {import('@playwright/test').Page} page
 * @param {string} memberId
 * @param {string} displayName
 */
async function generateIdentity(page, memberId, displayName) {
  await page.locator('#memberIdInput').fill(memberId);
  await page.locator('#displayNameInput').fill(displayName);
  await page.locator('#generateIdentityBtn').click();
  await expect(page.locator('#identitySummary')).toContainText(
    `Member ID: ${memberId}`,
    { timeout: 90_000 }
  );
  const publicKey = await page.locator('#publicKeyOutput').inputValue();
  const privateKey = await page.locator('#privateKeyInput').inputValue();
  expect(publicKey).toContain('BEGIN PGP PUBLIC KEY BLOCK');
  expect(privateKey).toContain('BEGIN PGP PRIVATE KEY BLOCK');
  return { publicKey, privateKey };
}

/**
 * Import an armored private key as the local identity.
 * @param {import('@playwright/test').Page} page
 */
async function importIdentity(page, memberId, displayName, privateKeyArmored, passphrase = '') {
  await page.locator('#memberIdInput').fill(memberId);
  await page.locator('#displayNameInput').fill(displayName);
  if (passphrase) await page.locator('#identityPassphraseInput').fill(passphrase);
  await page.locator('#privateKeyInput').fill(privateKeyArmored);
  await page.locator('#importIdentityBtn').click();
  await expect(page.locator('#identitySummary')).toContainText(
    `Member ID: ${memberId}`,
    { timeout: 60_000 }
  );
}

/**
 * Add a peer to the draft roster, mark them verified, and assert the entry
 * shows up in the draft list.
 */
async function addPeerAndVerify(alicePage, peerMemberId, peerDisplayName, peerPublicKey) {
  await alicePage.locator('#peerMemberIdInput').fill(peerMemberId);
  await alicePage.locator('#peerDisplayNameInput').fill(peerDisplayName);
  await alicePage.locator('#peerPublicKeyInput').fill(peerPublicKey);
  await alicePage.locator('#addPeerBtn').click();
  await expect(alicePage.locator('#draftRosterList')).toContainText(
    `${peerDisplayName} (${peerMemberId})`
  );
  await alicePage
    .locator(`#draftRosterList button[data-action="verify-draft"][data-member-id="${peerMemberId}"]`)
    .click();
}

/** Lock the draft roster as epoch 1. */
async function lockRoster(page) {
  await page.locator('#lockRosterBtn').click();
  await expect(page.locator('#epochSummary')).toContainText('Epoch: 1', {
    timeout: 30_000,
  });
}

/** Mark another member of the active roster verified locally. */
async function verifyActiveMember(page, memberId) {
  await page
    .locator(`#rosterList button[data-action="verify-active"][data-member-id="${memberId}"]`)
    .click();
}

/** Send a chat message; assumes composer is enabled. */
async function sendMessage(page, text) {
  await page.locator('#messageInput').fill(text);
  await page.locator('#sendBtn').click();
}

module.exports = {
  createRoom,
  acceptSecurityWarning,
  generateIdentity,
  importIdentity,
  addPeerAndVerify,
  lockRoster,
  verifyActiveMember,
  sendMessage,
};
