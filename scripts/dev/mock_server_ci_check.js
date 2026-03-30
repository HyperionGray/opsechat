#!/usr/bin/env node

/**
 * Simple test script to verify that the CI fix works
 * This script tests the mock server startup and basic connectivity
 */

const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const MOCK_SERVER_PATH = path.join(REPO_ROOT, 'tests', 'mock_server.py');

async function testServerStartup() {
  console.log('🧪 Testing mock server startup...');
  
  return new Promise((resolve, reject) => {
    // Start the mock server from repository root
    const serverProcess = spawn('python3', [MOCK_SERVER_PATH], {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: REPO_ROOT
    });

    let serverReady = false;
    let output = '';

    serverProcess.stdout.on('data', (data) => {
      const text = data.toString();
      output += text;
      console.log('Server output:', text.trim());
      
      if (text.includes('Mock server starting on') || text.includes('Running on')) {
        console.log('✅ Server appears to be starting...');
        
        // Wait a moment then test connectivity
        setTimeout(() => {
          testConnectivity()
            .then(() => {
              console.log('✅ Server connectivity test passed!');
              serverReady = true;
              serverProcess.kill();
              resolve(true);
            })
            .catch((err) => {
              console.error('❌ Server connectivity test failed:', err.message);
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

    // Timeout after 30 seconds
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
    console.log('🚀 Starting CI fix validation test...');
    await testServerStartup();
    console.log('🎉 All tests passed! The CI fix should work.');
    process.exit(0);
  } catch (error) {
    console.error('💥 Test failed:', error.message);
    console.log('This indicates the CI fix may need additional work.');
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}