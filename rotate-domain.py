#!/usr/bin/env python3
"""
Non-interactive domain registrar CLI for Porkbun.

Examples:
    python rotate-domain.py --search example.xyz
    python rotate-domain.py --buy example.xyz --years 1 --confirm
    python rotate-domain.py --list-owned
    python rotate-domain.py --get-pricing xyz
"""

import argparse
import json
import os
import sys
from pathlib import Path

from domain_manager import PorkbunAPIClient


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def load_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except Exception:
        return {}


def resolve_credentials(args):
    config = load_config()
    api_key = args.api_key or os.getenv("PORKBUN_API_KEY") or config.get("api_key")
    api_secret = (
        args.api_secret
        or os.getenv("PORKBUN_API_SECRET")
        or config.get("api_secret")
        or config.get("secret_key")
    )
    return api_key, api_secret


def print_json(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def require_credentials(args):
    api_key, api_secret = resolve_credentials(args)
    if not api_key or not api_secret:
        print_json(
            {
                "success": False,
                "error": (
                    "Missing API credentials. Provide --api-key/--api-secret, "
                    "set PORKBUN_API_KEY/PORKBUN_API_SECRET, or configure "
                    "~/.opsechat/domain_config.json."
                ),
            }
        )
        sys.exit(1)
    return PorkbunAPIClient(api_key, api_secret)


def main():
    parser = argparse.ArgumentParser(
        description="Simple domain management CLI for Porkbun"
    )
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--search", metavar="DOMAIN", help="Check if a domain is available"
    )
    action_group.add_argument(
        "--buy", metavar="DOMAIN", help="Purchase a domain (charges your account)"
    )
    action_group.add_argument(
        "--list-owned", action="store_true", help="List domains in your account"
    )
    action_group.add_argument(
        "--get-pricing", metavar="TLD", help="Get pricing for a TLD (e.g. xyz)"
    )

    parser.add_argument("--years", type=int, default=1, help="Registration years for --buy")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required safety flag when using --buy",
    )
    parser.add_argument("--api-key", help="Porkbun API key override")
    parser.add_argument("--api-secret", help="Porkbun API secret override")

    args = parser.parse_args()
    client = require_credentials(args)

    if args.search:
        print_json(client.search_domain(args.search))
        return 0

    if args.buy:
        if not args.confirm:
            print_json(
                {
                    "success": False,
                    "error": "Purchases require --confirm to reduce accidental charges.",
                }
            )
            return 2
        print_json(client.purchase_domain(args.buy, years=args.years))
        return 0

    if args.list_owned:
        print_json({"domains": client.list_domains()})
        return 0

    if args.get_pricing:
        print_json(client.get_pricing(args.get_pricing))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
