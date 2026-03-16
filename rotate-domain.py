#!/usr/bin/env python3
"""
Simple wrapper CLI for quick domain rotation operations.

Default behavior rotates to a new domain:
    python rotate-domain.py
"""

import argparse

from domain_rotation_cli import (
    configure_api,
    list_domains,
    rotate_domain,
    search_domains,
    show_status,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simple domain rotation wrapper for OpSecHat"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="Show domain rotation status")
    group.add_argument("--list", action="store_true", help="List owned domains")
    group.add_argument("--search", action="store_true", help="Search for cheap domains")
    group.add_argument("--config", action="store_true", help="Configure API credentials")
    args = parser.parse_args()

    if args.status:
        show_status()
        return
    if args.list:
        list_domains()
        return
    if args.search:
        search_domains()
        return
    if args.config:
        configure_api()
        return

    # Default action: rotate to a new domain.
    rotate_domain()


if __name__ == "__main__":
    main()
