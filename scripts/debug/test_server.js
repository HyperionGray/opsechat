#!/usr/bin/env node
/**
 * Start mock server and test key endpoints.
 */

const { spawn } = require('child_process');

async function testServer() {
  console.log('Testing mock server startup...');

  const serverProcess = spawn('python3', ['tests/mock_server.py'], {
    stdio: 'pipe'
  });

  serverProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log('Server:', output.trim());
  });

  serverProcess.stderr.on('data', (data) => {
    console.error('Server Error:', data.toString().trim());
  });

  await new Promise((resolve) => setTimeout(resolve, 3000));

  try {
    const healthResponse = await fetch('http://127.0.0.1:5001/health');
    const healthJson = await healthResponse.json();
    console.log('Health check response:', healthJson);

    const mainResponse = await fetch('http://127.0.0.1:5001/test-path-12345');
    console.log('Main endpoint status:', mainResponse.status);
    console.log('Server test passed.');
  } catch (error) {
    console.error('Server test failed:', error.message);
  }

  serverProcess.kill();
}

if (require.main === module) {
  testServer().catch(console.error);
}

module.exports = { testServer };
