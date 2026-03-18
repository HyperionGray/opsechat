#!/usr/bin/env python3
"""
Compatibility wrapper for domain rotation CLI.

This script preserves the documented `python rotate-domain.py ...` entrypoint
while delegating all functionality to domain_rotation_cli.py.
"""

from domain_rotation_cli import main


if __name__ == "__main__":
    main()
