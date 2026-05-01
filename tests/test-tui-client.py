#!/usr/bin/env python3
"""
Simple test client for TUI chat server
Tests basic connectivity and message exchange without TUI
"""

import sys
from pathlib import Path
import socket
import json
import time

# Add reorganized Python source tree to path.
SRC_PYTHON = Path(__file__).resolve().parents[1] / "src" / "python"
sys.path.insert(0, str(SRC_PYTHON))

def test_client(host='127.0.0.1', port=5555):
    """Test basic client functionality"""
    print(f"[*] Connecting to {host}:{port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        print("[✓] Connected to server")
        
        # Receive welcome message
        buffer = ""
        while True:
            data = sock.recv(4096).decode('utf-8')
            if not data:
                break
            buffer += data
            if '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                msg = json.loads(line)
                if msg.get('type') == 'welcome':
                    print(f"[✓] Received welcome: {msg.get('message')}")
                    print(f"[✓] Assigned username: {msg.get('username')}")
                    break
        
        # Send a test message
        test_msg = {
            'type': 'message',
            'message': 'Hello from test client!'
        }
        sock.send((json.dumps(test_msg) + '\n').encode())
        print("[✓] Sent test message")
        
        # Wait a bit for response
        time.sleep(0.5)
        
        # Receive our message back (broadcasted)
        try:
            data = sock.recv(4096).decode('utf-8')
            if data:
                buffer += data
                if '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    msg = json.loads(line)
                    if msg.get('type') == 'message':
                        print(f"[✓] Received message: [{msg.get('username')}] {msg.get('message')}")
        except socket.timeout:
            print("[!] No message received (timeout)")
        
        sock.close()
        print("[✓] Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"[✗] Test failed: {e}")
        return False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Test TUI Chat Client')
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    args = parser.parse_args()
    
    success = test_client(args.host, args.port)
    sys.exit(0 if success else 1)
