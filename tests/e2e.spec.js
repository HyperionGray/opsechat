/**
 * Backward-compatible E2E test entrypoint.
 *
 * `npm run test:e2e` targets this file, and this file loads every split
 * `*.e2e.spec.js` suite so the command runs the full E2E coverage instead of
 * a placeholder skip.
 */

const fs = require('fs');
const path = require('path');

const testDir = __dirname;

const splitSuites = fs
  .readdirSync(testDir)
  .filter((name) => name.endsWith('.e2e.spec.js'))
  .sort();

if (splitSuites.length === 0) {
  throw new Error('No split E2E suites found (expected *.e2e.spec.js files).');
}

for (const suite of splitSuites) {
  // eslint-disable-next-line import/no-dynamic-require, global-require
  require(path.join(testDir, suite));
}
