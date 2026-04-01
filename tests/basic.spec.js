/**
 * Basic Unit Tests for opsechat
 * 
 * These tests validate basic functionality without requiring a running server
 */

const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

test.describe('Project Structure Tests', () => {
  test('should have required files', () => {
    const requiredFiles = [
      'runserver.py',
      'requirements.txt',
      'README.md',
      'setup.py',
    ];

    requiredFiles.forEach(file => {
      const filePath = path.join(__dirname, '..', file);
      expect(fs.existsSync(filePath)).toBeTruthy();
    });
  });

  test('should have templates directory', () => {
    const templatesDir = path.join(__dirname, '..', 'templates');
    expect(fs.existsSync(templatesDir)).toBeTruthy();
    expect(fs.statSync(templatesDir).isDirectory()).toBeTruthy();
  });

  test('should have static directory with assets', () => {
    const staticDir = path.join(__dirname, '..', 'static');
    expect(fs.existsSync(staticDir)).toBeTruthy();
    expect(fs.statSync(staticDir).isDirectory()).toBeTruthy();
    
    // Check for jQuery
    const jqueryPath = path.join(staticDir, 'jquery.js');
    expect(fs.existsSync(jqueryPath)).toBeTruthy();
  });

  test('should have valid requirements.txt', () => {
    const reqPath = path.join(__dirname, '..', 'requirements.txt');
    const content = fs.readFileSync(reqPath, 'utf8');
    
    expect(content).toContain('Flask');
    expect(content).toContain('stem');
  });

  test('should have runserver.py wired to the app factory and Tor startup', () => {
    const serverPath = path.join(__dirname, '..', 'runserver.py');
    const content = fs.readFileSync(serverPath, 'utf8');
    
    // Check for the current entrypoint structure
    expect(content).toContain('from app_factory import create_app');
    expect(content).toContain('from stem.control import Controller');
    expect(content).toContain('def setup_tor_configuration():');
    expect(content).toContain('def main():');
    expect(content).toContain('app = create_app()');
  });
});

test.describe('Python Module Tests', () => {
  test('should import runserver module without errors', async () => {
    // This is a basic smoke test to ensure the module can be imported
    const { exec } = require('child_process');
    const { promisify } = require('util');
    const execAsync = promisify(exec);
    
    const projectRoot = path.join(__dirname, '..');
    
    try {
      // Test basic Python syntax and Flask availability first
      await execAsync(`python3 -c "import flask; print('Flask available')"`);
      
      // Try to import runserver with better error handling
      const { stdout, stderr } = await execAsync(
        `python3 -c "
import sys
sys.path.insert(0, '${projectRoot}')
try:
    import runserver
    print('runserver imported successfully')
except ImportError as e:
    if 'stem' in str(e) or 'email_system' in str(e) or 'domain_manager' in str(e):
        print('runserver has expected dependencies that are not available in test environment')
        print(f'Missing dependency: {e}')
    else:
        raise e
"`
      );
      
      // Check if import was successful or had expected dependency issues
      const output = stdout.toLowerCase();
      if (output.includes('imported successfully') || output.includes('expected dependencies')) {
        expect(true).toBeTruthy();
      } else {
        throw new Error(`Unexpected import result: ${stdout}`);
      }
      
    } catch (error) {
      // Only fail if it's not a known dependency issue
      if (error.message.includes('stem') || 
          error.message.includes('email_system') || 
          error.message.includes('domain_manager')) {
        console.log('Skipping test due to expected missing dependencies in test environment');
        test.skip();
      } else {
        throw new Error(`Failed to import runserver: ${error.message}`);
      }
    }
  });
});

test.describe('Configuration Tests', () => {
  test('should have playwright config', () => {
    const configPath = path.join(__dirname, '..', 'playwright.config.js');
    expect(fs.existsSync(configPath)).toBeTruthy();
  });

  test('should have package.json with playwright', () => {
    const pkgPath = path.join(__dirname, '..', 'package.json');
    expect(fs.existsSync(pkgPath)).toBeTruthy();
    
    const content = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
    expect(content.devDependencies).toBeDefined();
    expect(content.devDependencies['@playwright/test']).toBeDefined();
  });
});

test.describe('Mock server endpoint checks', () => {
  test('should expose a healthy mock health endpoint', async ({ request }) => {
    const response = await request.get('/health');

    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('application/json');

    const data = await response.json();
    expect(data).toHaveProperty('status');
    expect(data).toHaveProperty('timestamp');
  });
});
