#!/usr/bin/env python3
"""
Backward-compatible entrypoint for domain rotation CLI.

Some documentation and operator runbooks reference `python rotate-domain.py`.
This wrapper preserves that command while delegating to the maintained CLI
implementation in domain_rotation_cli.py.
"""

from domain_rotation_cli import main


if __name__ == "__main__":
    main()
