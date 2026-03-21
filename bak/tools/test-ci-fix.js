#!/usr/bin/env node

/**
 * Archived CI investigation script.
 * Kept under bak/tools to avoid root-level clutter.
 */

const { spawn } = require('child_process');
const http = require('http');

async function testServerStartup() {
  console.log('Testing mock server startup...');

  return new Promise((resolve, reject) => {
    const serverProcess = spawn('python3', ['tests/mock_server.py'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let serverReady = false;

    serverProcess.stdout.on('data', (data) => {
      const text = data.toString();
      console.log('Server output:', text.trim());

      if (text.includes('Mock server starting on') || text.includes('Running on')) {
        console.log('Server appears to be starting...');
        setTimeout(() => {
          testConnectivity()
            .then(() => {
              console.log('Server connectivity test passed.');
              serverReady = true;
              serverProcess.kill();
              resolve(true);
            })
            .catch((err) => {
              console.error('Server connectivity test failed:', err.message);
              serverProcess.kill();
              reject(err);
            });
        }, 2000);
      }
    });

    serverProcess.stderr.on('data', (data) => {
      console.error('Server error:', data.toString());
    });

    serverProcess.on('close', (code) => {
      if (!serverReady) {
        reject(new Error(`Server exited with code ${code} before becoming ready`));
      }
    });

    setTimeout(() => {
      if (!serverReady) {
        serverProcess.kill();
        reject(new Error('Server startup timeout'));
      }
    }, 30000);
  });
}

async function testConnectivity() {
  return new Promise((resolve, reject) => {
    const req = http.get('http://127.0.0.1:5001/', (res) => {
      console.log(`Status: ${res.statusCode}`);
      if (res.statusCode === 200) {
        resolve();
      } else {
        reject(new Error(`Unexpected status code: ${res.statusCode}`));
      }
    });

    req.on('error', (err) => {
      reject(err);
    });

    req.setTimeout(5000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

async function main() {
  try {
    console.log('Starting CI fix validation test...');
    await testServerStartup();
    console.log('All tests passed.');
    process.exit(0);
  } catch (error) {
    console.error('Test failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
