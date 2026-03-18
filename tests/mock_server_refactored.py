#!/usr/bin/env python3
"""
Compatibility wrapper for legacy references.

The refactored mock server now lives in tests/mock_server.py. This module stays
in place so older scripts that call mock_server_refactored.py continue to work.
"""

from mock_server import main


if __name__ == "__main__":
    main()
