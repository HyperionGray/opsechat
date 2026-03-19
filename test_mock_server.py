#!/usr/bin/env python3
"""
Simple test script to verify mock server can start and respond
"""

import sys
import os
import time
import subprocess
import requests
def run_mock_server_check():
    """Run a health-check flow against the mock server process."""
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
        
        # Poll health check while the process boots.
        last_error = None
        for _ in range(15):
            if server_process.poll() is not None:
                break

            try:
                response = requests.get('http://127.0.0.1:5001/health', timeout=2)
                print(f"Health check status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"Health check response: {data}")
                    print("✅ Mock server is working correctly!")
                    return True
            except requests.RequestException as e:
                last_error = e

            time.sleep(1)

        if last_error is not None:
            print(f"❌ Could not connect to mock server: {last_error}")
        else:
            print("❌ Mock server exited before health check succeeded")
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
    """Test that the mock server can start and respond to health checks."""
    assert run_mock_server_check() is True


if __name__ == '__main__':
    success = run_mock_server_check()
    sys.exit(0 if success else 1)