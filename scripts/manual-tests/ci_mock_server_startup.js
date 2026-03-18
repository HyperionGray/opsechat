#!/usr/bin/env node
/**
 * Validate mock server startup and basic connectivity.
 *
 * This script is intended for manual CI debugging.
 */

const { spawn } = require('child_process');
const http = require('http');

async function testConnectivity() {
  return new Promise((resolve, reject) => {
    const req = http.get('http://127.0.0.1:5001/', (res) => {
      if (res.statusCode === 200) {
        resolve();
        return;
      }
      reject(new Error(`Unexpected status code: ${res.statusCode}`));
    });

    req.on('error', reject);
    req.setTimeout(5000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

async function testServerStartup() {
  console.log('Testing mock server startup');

  return new Promise((resolve, reject) => {
    const serverProcess = spawn('python3', ['tests/mock_server.py'], {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let ready = false;

    serverProcess.stdout.on('data', (data) => {
      const text = data.toString();
      console.log(`server stdout: ${text.trim()}`);

      if (text.includes('Mock server starting on') || text.includes('Running on')) {
        setTimeout(() => {
          testConnectivity()
            .then(() => {
              ready = true;
              serverProcess.kill();
              resolve(true);
            })
            .catch((err) => {
              serverProcess.kill();
              reject(err);
            });
        }, 2000);
      }
    });

    serverProcess.stderr.on('data', (data) => {
      console.error(`server stderr: ${data.toString().trim()}`);
    });

    serverProcess.on('close', (code) => {
      if (!ready) {
        reject(new Error(`Server exited before readiness (code ${code})`));
      }
    });

    setTimeout(() => {
      if (!ready) {
        serverProcess.kill();
        reject(new Error('Server startup timeout'));
      }
    }, 30000);
  });
}

async function main() {
  try {
    await testServerStartup();
    console.log('Manual CI startup check passed');
    process.exit(0);
  } catch (error) {
    console.error(`Manual CI startup check failed: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
