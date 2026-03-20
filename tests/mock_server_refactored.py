#!/usr/bin/env python3
"""
Compatibility shim for older scripts that invoke mock_server_refactored.py.

The active implementation lives in tests/mock_server.py to keep behavior
consistent and avoid code drift between duplicate mock servers.
"""

from mock_server import app, main

__all__ = ["app", "main"]


if __name__ == "__main__":
    main()