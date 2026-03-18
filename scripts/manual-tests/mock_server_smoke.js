#!/usr/bin/env node
/**
 * Basic smoke test for the Python mock server.
 */

const { spawn } = require('child_process');

async function testServer() {
  console.log('Starting mock server smoke test');

  const serverProcess = spawn('python3', ['tests/mock_server.py'], {
    stdio: 'pipe',
  });

  serverProcess.stdout.on('data', (data) => {
    console.log(`server stdout: ${data.toString().trim()}`);
  });

  serverProcess.stderr.on('data', (data) => {
    console.error(`server stderr: ${data.toString().trim()}`);
  });

  await new Promise((resolve) => setTimeout(resolve, 3000));

  try {
    const healthResponse = await fetch('http://127.0.0.1:5001/health');
    const healthData = await healthResponse.json();
    console.log(`health endpoint status: ${healthResponse.status}`);
    console.log(`health payload: ${JSON.stringify(healthData)}`);

    const mainResponse = await fetch('http://127.0.0.1:5001/test-path-12345');
    console.log(`main endpoint status: ${mainResponse.status}`);

    if (healthResponse.ok && mainResponse.status === 200) {
      console.log('Mock server smoke test passed');
      return;
    }

    throw new Error('Unexpected response status from mock server');
  } finally {
    serverProcess.kill();
  }
}

if (require.main === module) {
  testServer().catch((err) => {
    console.error(`Mock server smoke test failed: ${err.message}`);
    process.exit(1);
  });
}

module.exports = { testServer };
