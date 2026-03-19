/**
 * DEPRECATED: This file has been split into smaller, more maintainable test files.
 * 
 * The original e2e.spec.js (641 lines) has been refactored into focused test files:
 * 
 * - landing-page.e2e.spec.js - Landing page and root path tests (88 lines)
 * - chat-interface.e2e.spec.js - Chat functionality tests (165 lines)
 * - email-burner.e2e.spec.js - Email burner functionality (78 lines)
 * - security-session.e2e.spec.js - Security and session tests (166 lines)
 * - user-workflow.e2e.spec.js - Complete workflows and concurrent users (91 lines)
 * - error-validation.e2e.spec.js - Error handling tests (98 lines)
 * 
 * Total: 686 lines across 6 focused test files (vs 641 lines in single file)
 * Note: Slight increase due to file headers and better organization
 * Each file is focused and maintainable (all < 200 lines)
 * 
 * This file is kept for backward compatibility. All tests now run from the new files.
 * Original file archived at: bak/tests/e2e.spec.js.deprecated
 */

const { test } = require('@playwright/test');

test.describe('Deprecated - See individual test files', () => {
  test.skip('All tests moved to individual files', () => {
    // This is a placeholder - see file header for new test locations
  });
});
