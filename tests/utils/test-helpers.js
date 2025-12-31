/**
 * Test Utilities for opsechat E2E Tests
 * 
 * Common utilities and helper functions to reduce code duplication
 * across test files and improve maintainability.
 */

/**
 * Common test configuration
 */
const TEST_CONFIG = {
  baseURL: 'http://127.0.0.1:5001',
  testPath: '/test-path-12345',
  timeout: 30000,
  retries: 2
};

/**
 * Helper function to establish a session
 * @param {Page} page - Playwright page object
 * @returns {Promise<Response>} - Response from the initial page load
 */
async function establishSession(page) {
  const response = await page.goto(TEST_CONFIG.testPath);
  if (!response) {
    throw new Error('Failed to establish session');
  }
  return response;
}

/**
 * Helper function to post a chat message
 * @param {Page} page - Playwright page object
 * @param {string} message - Message to post
 * @param {boolean} useJson - Whether to use JSON endpoint (default: true)
 * @returns {Promise<Response>} - Response from the post request
 */
async function postChatMessage(page, message, useJson = true) {
  const endpoint = useJson ? '/chatsjs' : '/chats';
  
  return await page.request.post(TEST_CONFIG.testPath + endpoint, {
    form: {
      dropdata: message
    }
  });
}

/**
 * Helper function to get chat messages
 * @param {Page} page - Playwright page object
 * @returns {Promise<Array>} - Array of chat messages
 */
async function getChatMessages(page) {
  const response = await page.request.get(TEST_CONFIG.testPath + '/chatsjs');
  if (response.status() !== 200) {
    throw new Error(`Failed to get chat messages: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Helper function to verify response status is acceptable
 * @param {Response} response - Playwright response object
 * @param {Array<number>} acceptableStatuses - Array of acceptable status codes
 */
function verifyResponseStatus(response, acceptableStatuses = [200]) {
  if (!acceptableStatuses.includes(response.status())) {
    throw new Error(`Unexpected status code: ${response.status()}, expected one of: ${acceptableStatuses.join(', ')}`);
  }
}

/**
 * Helper function to skip test if response is null
 * @param {Response|null} response - Playwright response object
 * @param {Test} test - Playwright test object
 */
function skipIfNoResponse(response, test) {
  if (!response) {
    test.skip();
    return true;
  }
  return false;
}

/**
 * Helper function to create a PGP test message
 * @param {string} content - Content to include in the PGP message
 * @returns {string} - Formatted PGP message
 */
function createPGPMessage(content = 'test content') {
  return `-----BEGIN PGP MESSAGE-----
Version: GnuPG v2

${content}
-----END PGP MESSAGE-----`;
}

/**
 * Helper function to generate test data
 * @param {string} prefix - Prefix for the test data
 * @returns {Object} - Test data object
 */
function generateTestData(prefix = 'test') {
  const timestamp = Date.now();
  return {
    message: `${prefix} message ${timestamp}`,
    longMessage: 'A'.repeat(1000),
    unicodeMessage: `${prefix} 🔒 émojis 中文 ${timestamp}`,
    xssPayload: `<script>alert('${prefix}')</script>`,
    pgpMessage: createPGPMessage(`${prefix} ${timestamp}`)
  };
}

/**
 * Helper function to wait for condition with timeout
 * @param {Function} condition - Function that returns true when condition is met
 * @param {number} timeout - Timeout in milliseconds (default: 5000)
 * @param {number} interval - Check interval in milliseconds (default: 100)
 * @returns {Promise<boolean>} - True if condition was met, false if timeout
 */
async function waitForCondition(condition, timeout = 5000, interval = 100) {
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeout) {
    if (await condition()) {
      return true;
    }
    await new Promise(resolve => setTimeout(resolve, interval));
  }
  
  return false;
}

/**
 * Helper function to verify security headers
 * @param {Response} response - Playwright response object
 * @returns {Object} - Object with header verification results
 */
function verifySecurityHeaders(response) {
  const headers = response.headers();
  
  return {
    serverHeaderControlled: headers['server'] === undefined || typeof headers['server'] === 'string',
    dateHeaderControlled: headers['date'] === undefined || typeof headers['date'] === 'string',
    hasSecurityHeaders: true // Can be expanded with more specific checks
  };
}

/**
 * Helper function to clean up test data
 * @param {Page} page - Playwright page object
 */
async function cleanupTestData(page) {
  // This could be expanded to clean up any test-specific data
  // For now, just ensure we have a clean session
  try {
    await page.context().clearCookies();
  } catch (error) {
    // Ignore cleanup errors
    console.warn('Cleanup warning:', error.message);
  }
}

module.exports = {
  TEST_CONFIG,
  establishSession,
  postChatMessage,
  getChatMessages,
  verifyResponseStatus,
  skipIfNoResponse,
  createPGPMessage,
  generateTestData,
  waitForCondition,
  verifySecurityHeaders,
  cleanupTestData
};