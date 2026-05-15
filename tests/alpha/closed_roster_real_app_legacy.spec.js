const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { test, expect } = require('@playwright/test');

const PROJECT_PORTS = {
  'chromium-headless': 5111,
  'firefox-headless': 5112,
  'webkit-headless': 5113,
  'chromium-headed': 5114,
  'firefox-headed': 5115,
};

async function waitForServer(baseURL, timeoutMs = 30000) {
  const start = Date.now();
  let lastError = null;

  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(`${baseURL}/health`);
      if (response.ok) {
        return;
      }
      lastError = new Error(`health returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  throw lastError || new Error(`Timed out waiting for ${baseURL}`);
}

async function createRoom(page, baseURL) {
  await page.goto(`${baseURL}/chat`);
  await expect(page.locator('#createRoomBtn')).toBeVisible();
  await page.locator('#createRoomBtn').click();
  await expect(page).toHaveURL(/\/chat\/room\/[\w-]+/, { timeout: 10000 });
  return page.url();
}

async function acceptSecurityWarning(page) {
  const warning = page.locator('#securityWarning');
  if (await warning.isVisible()) {
    await page.locator('#acceptSecurityWarningBtn').click();
    await expect(warning).toBeHidden();
  }
}

async function generateIdentity(page, memberId, displayName) {
  await page.locator('#memberIdInput').fill(memberId);
  await page.locator('#displayNameInput').fill(displayName);
  await page.locator('#generateIdentityBtn').click();
  await expect(page.locator('#identitySummary')).toContainText(`Member ID: ${memberId}`, {
    timeout: 60000,
  });

  const publicKey = await page.locator('#publicKeyOutput').inputValue();
  const privateKey = await page.locator('#privateKeyInput').inputValue();

  expect(publicKey).toContain('BEGIN PGP PUBLIC KEY BLOCK');
  expect(privateKey).toContain('BEGIN PGP PRIVATE KEY BLOCK');

  return { publicKey, privateKey };
}

async function importIdentity(page, memberId, displayName, privateKeyArmored) {
  await page.locator('#memberIdInput').fill(memberId);
  await page.locator('#displayNameInput').fill(displayName);
  await page.locator('#privateKeyInput').fill(privateKeyArmored);
  await page.locator('#importIdentityBtn').click();
  await expect(page.locator('#identitySummary')).toContainText(`Member ID: ${memberId}`, {
    timeout: 30000,
  });
}

test.describe('Closed-Roster OpenPGP Real-App Smoke Tests', () => {
  test.describe.configure({ mode: 'serial' });

  let serverProcess;
  let baseURL;

  test.beforeAll(async ({}, testInfo) => {
    const port = PROJECT_PORTS[testInfo.project.name] || 5199;
    baseURL = `http://127.0.0.1:${port}`;

    serverProcess = spawn('python3', ['tests/real_app_server.py'], {
      cwd: path.resolve(__dirname, '..'),
      env: {
        ...process.env,
        OPSECHAT_PLAYWRIGHT_PORT: String(port),
      },
      stdio: 'pipe',
    });

    let stderr = '';
    serverProcess.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    try {
      await waitForServer(baseURL);
    } catch (error) {
      if (serverProcess && !serverProcess.killed) {
        serverProcess.kill('SIGTERM');
      }
      throw new Error(`${error.message}\n${stderr}`.trim());
    }
  });

  test.afterAll(async () => {
    if (!serverProcess || serverProcess.killed) {
      return;
    }

    serverProcess.kill('SIGTERM');
    await new Promise((resolve) => {
      serverProcess.once('exit', resolve);
      setTimeout(resolve, 5000);
    });
  });

  test('exports and restores a session-scoped private key backup', async ({ page }) => {
    test.setTimeout(120000);

    await createRoom(page, baseURL);
    await acceptSecurityWarning(page);
    await generateIdentity(page, 'alice', 'Alice');

    const downloadPromise = page.waitForEvent('download');
    await page.locator('#downloadPrivateKeyBtn').click();
    const download = await downloadPromise;
    const downloadPath = await download.path();
    const downloadedPrivateKey = fs.readFileSync(downloadPath, 'utf8');

    expect(downloadedPrivateKey).toContain('BEGIN PGP PRIVATE KEY BLOCK');
    await expect(page.locator('#identitySummary')).not.toContainText(
      'Not downloaded in this browser session',
    );
    await expect(page.locator('#identityRecovery')).toContainText('Last private-key export:');

    page.once('dialog', (dialog) => dialog.accept());
    await page.locator('#clearIdentityBtn').click();
    await expect(page.locator('#identitySummary')).toContainText('No local identity configured.');

    await importIdentity(page, 'alice', 'Alice', downloadedPrivateKey);
    await expect(page.locator('#identityRecovery')).toContainText('Last private-key export:');
  });

  test('bootstraps a room and decrypts an encrypted message between two members', async ({ browser }) => {
    test.setTimeout(180000);

    const aliceContext = await browser.newContext({ acceptDownloads: true });
    const bobContext = await browser.newContext({ acceptDownloads: true });
    const alicePage = await aliceContext.newPage();
    const bobPage = await bobContext.newPage();

    try {
      const roomUrl = await createRoom(alicePage, baseURL);
      await acceptSecurityWarning(alicePage);
      await generateIdentity(alicePage, 'alice', 'Alice');

      await bobPage.goto(roomUrl);
      await acceptSecurityWarning(bobPage);
      const bobIdentity = await generateIdentity(bobPage, 'bob', 'Bob');

      await alicePage.locator('#peerMemberIdInput').fill('bob');
      await alicePage.locator('#peerDisplayNameInput').fill('Bob');
      await alicePage.locator('#peerPublicKeyInput').fill(bobIdentity.publicKey);
      await alicePage.locator('#addPeerBtn').click();
      await expect(alicePage.locator('#draftRosterList')).toContainText('Bob (bob)');
      await alicePage.locator('#draftRosterList button[data-action="verify-draft"][data-member-id="bob"]').click();
      await alicePage.locator('#lockRosterBtn').click();

      await expect(alicePage.locator('#epochSummary')).toContainText('Epoch: 1', {
        timeout: 15000,
      });
      await expect(bobPage.locator('#epochSummary')).toContainText('Epoch: 1', {
        timeout: 15000,
      });

      await bobPage.locator('#rosterList button[data-action="verify-active"][data-member-id="alice"]').click();
      await expect(alicePage.locator('#composerState')).toContainText(
        'Ready: this message will be signed and encrypted to the full roster.',
      );

      const plaintext = 'Alpha real-app smoke message';
      await alicePage.locator('#messageInput').fill(plaintext);
      await alicePage.locator('#sendBtn').click();

      await expect(bobPage.locator('.message-body')).toContainText(plaintext, {
        timeout: 20000,
      });
      await expect(bobPage.locator('.message-note')).toContainText('Verified locally', {
        timeout: 20000,
      });
    } finally {
      await aliceContext.close();
      await bobContext.close();
    }
  });
});
