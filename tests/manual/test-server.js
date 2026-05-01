#!/usr/bin/env node
/**
 * Simple test script to verify the mock server starts correctly
 * This can be used to debug server startup issues
 */

const { spawn } = require('child_process');
const http = require('http');

async function testServer() {
  console.log('Testing mock server startup...');
  
  // Start the mock server
  const serverProcess = spawn('python3', ['tests/mock_server.py'], {
    stdio: 'pipe'
  });

  let serverOutput = '';
  
  serverProcess.stdout.on('data', (data) => {
    const output = data.toString();
    serverOutput += output;
    console.log('Server:', output.trim());
  });

  serverProcess.stderr.on('data', (data) => {
    console.error('Server Error:', data.toString().trim());
  });

  // Wait for server to start
  await new Promise(resolve => setTimeout(resolve, 3000));

  // Test health endpoint
  try {
    const response = await fetch('http://127.0.0.1:5001/health');
    const data = await response.json();
    console.log('Health check response:', data);
    
    // Test main endpoint
    const mainResponse = await fetch('http://127.0.0.1:5001/test-path-12345');
    console.log('Main endpoint status:', mainResponse.status);
    
    console.log('✅ Server test passed!');
  } catch (error) {
    console.error('❌ Server test failed:', error.message);
  }

  // Clean up
  serverProcess.kill();
}

// Run if called directly
if (require.main === module) {
  testServer().catch(console.error);
}

module.exports = { testServer };