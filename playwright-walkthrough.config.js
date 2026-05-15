// @ts-check
/**
 * One-off config used by `npm run test:alpha:walkthrough-evidence`.
 *
 * Same shape as the default alpha config, but:
 *   - records video for every run
 *   - records a trace for every run
 *   - captures a final screenshot on success
 *
 * Used to capture a reviewable artifact of the headless walkthrough run
 * for releases / PR evidence.
 */
const base = require('./playwright.config.js');

module.exports = {
  ...base,
  use: {
    ...(base.use || {}),
    video: 'on',
    trace: 'on',
    screenshot: 'on',
  },
};
