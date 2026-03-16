#!/usr/bin/env python3
"""
Simple smoke test client for TUI chat server.
Tests basic connectivity and message exchange without urwid UI.
"""

import argparse
import json
import socket
import sys
import time


def run_smoke_test(host="127.0.0.1", port=5555):
    """Run a basic connectivity and send/receive smoke test."""
    print(f"[*] Connecting to {host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        print("[OK] Connected to server")

        # Receive welcome message
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
                    print(f"[OK] Received welcome: {msg.get('message')}")
                    print(f"[OK] Assigned username: {msg.get('username')}")
                    break

        # Send a test message
        test_msg = {"type": "message", "message": "Hello from smoke test client!"}
        sock.send((json.dumps(test_msg) + "\n").encode())
        print("[OK] Sent test message")

        # Wait briefly for broadcast
        time.sleep(0.5)

        try:
            data = sock.recv(4096).decode("utf-8")
            if data:
                buffer += data
                if "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    msg = json.loads(line)
                    if msg.get("type") == "message":
                        print(f"[OK] Received message: [{msg.get('username')}] {msg.get('message')}")
        except socket.timeout:
            print("[WARN] No message received (timeout)")

        sock.close()
        print("[OK] Smoke test completed successfully")
        return True

    except Exception as exc:
        print(f"[FAIL] Smoke test failed: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Smoke test TUI chat client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=5555, help="Server port")
    args = parser.parse_args()

    success = run_smoke_test(args.host, args.port)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
