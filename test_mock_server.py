#!/usr/bin/env python3
"""
Simple test script to verify mock server can start and respond
"""

import os
import subprocess
import sys
import time

import requests


def run_mock_server_smoke_test():
    """Run mock-server startup and health-check validation."""
    print("Testing mock server startup...")
    
    # Start the mock server in a subprocess
    server_process = None
    try:
        server_process = subprocess.Popen(
            [sys.executable, 'tests/mock_server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # Wait a bit for server to start
        time.sleep(3)
        
        # Test health check endpoint
        try:
            response = requests.get('http://127.0.0.1:5001/health', timeout=10)
            print(f"Health check status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Health check response: {data}")
                print("✅ Mock server is working correctly!")
                return True
            else:
                print(f"❌ Health check failed with status {response.status_code}")
                return False
        except requests.RequestException as e:
            print(f"❌ Could not connect to mock server: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting mock server: {e}")
        return False
    finally:
        if server_process:
            server_process.terminate()
            server_process.wait()
    
    return False


def test_mock_server():
    """Pytest entrypoint: server should boot and answer /health."""
    assert run_mock_server_smoke_test()

if __name__ == '__main__':
    success = run_mock_server_smoke_test()
    sys.exit(0 if success else 1)