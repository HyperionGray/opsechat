#!/usr/bin/env python3
"""
OpSecChat TUI Client Launcher

Launches the TUI-based chat client to connect to a server.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tui.client import main

if __name__ == '__main__':
    main()
