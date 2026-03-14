#!/usr/bin/env python3
"""
Manual smoke-test client for the TUI chat server.

Usage:
  1) Start server: python tui-server.py
  2) Run this script: python scripts/tui_smoke_client.py
"""

import argparse
import json
import socket
import sys
import time


def run_smoke_test(host: str = "127.0.0.1", port: int = 5555) -> bool:
    """Basic connectivity and send/receive validation."""
    print(f"[*] Connecting to {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        sock.connect((host, port))
        print("[✓] Connected to server")

        buffer = ""
        while True:
            data = sock.recv(4096).decode("utf-8")
            if not data:
                break
            buffer += data
            if "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                msg = json.loads(line)
                if msg.get("type") == "welcome":
                    print(f"[✓] Received welcome: {msg.get('message')}")
                    print(f"[✓] Assigned username: {msg.get('username')}")
                    break

        test_msg = {"type": "message", "message": "Hello from smoke test client!"}
        sock.send((json.dumps(test_msg) + "\n").encode())
        print("[✓] Sent test message")

        time.sleep(0.5)
        try:
            data = sock.recv(4096).decode("utf-8")
            if data:
                buffer += data
                if "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    msg = json.loads(line)
                    if msg.get("type") == "message":
                        print(f"[✓] Received broadcast: [{msg.get('username')}] {msg.get('message')}")
        except socket.timeout:
            print("[!] No broadcast received (timeout)")

        print("[✓] Smoke test completed")
        return True
    except Exception as exc:
        print(f"[✗] Smoke test failed: {exc}")
        return False
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description="Manual smoke test for TUI chat server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=5555, help="Server port")
    args = parser.parse_args()
    success = run_smoke_test(args.host, args.port)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
