#!/usr/bin/env python3
"""
Compatibility wrapper for domain rotation operations.

Some docs and older automation reference `python rotate-domain.py`.
This script delegates to the maintained domain_rotation_cli module.
"""

import argparse
import sys

import domain_rotation_cli as cli


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Legacy-compatible domain rotation CLI wrapper"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--search",
        action="store_true",
        help="Search for available cheap domains",
    )
    group.add_argument(
        "--buy",
        metavar="DOMAIN",
        help="Purchase and activate a specific domain (uses existing budget controls)",
    )
    group.add_argument(
        "--list-owned",
        action="store_true",
        help="List currently owned domains",
    )
    group.add_argument(
        "--get-pricing",
        metavar="TLD",
        help="Get pricing for a specific TLD",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Show budget/domain status",
    )

    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-confirm purchases where applicable",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=1,
        help="Registration years when used with --buy (default: 1)",
    )
    return parser.parse_args(argv)


def _run_buy(domain, auto_confirm, years):
    manager, config = cli.get_manager()
    if years < 1:
        print("Years must be >= 1")
        return 1

    search_result = manager.api_client.search_domain(domain)
    if not search_result.get("available"):
        print(f"Domain is not available: {domain}")
        return 1

    raw_price = search_result.get("price")
    try:
        price = float(str(raw_price).replace("$", "").replace("€", ""))
    except (TypeError, ValueError):
        print(f"Unable to parse domain price for {domain}: {raw_price}")
        return 1

    print(f"Found {domain} for ${price}")
    if not auto_confirm:
        confirm = input("Proceed with purchase? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Purchase cancelled.")
            return 0

    success = manager.purchase_domain_if_budget_allows(domain, price, years=years)
    if not success:
        print("Purchase failed (budget/API error).")
        return 1

    manager.active_domain = domain
    cli.save_manager_state(manager, config)
    print(f"Successfully purchased and activated: {domain}")
    return 0


def _run_get_pricing(tld):
    manager, _config = cli.get_manager()
    pricing = manager.api_client.get_pricing(tld)
    if not pricing:
        print(f"No pricing returned for TLD: {tld}")
        return 1

    print(f"TLD: .{pricing.get('tld', tld)}")
    print(f"Registration: {pricing.get('registration')}")
    print(f"Renewal: {pricing.get('renewal')}")
    print(f"Transfer: {pricing.get('transfer')}")
    return 0


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])

    if args.search:
        cli.run_command("search")
        return 0
    if args.list_owned:
        cli.run_command("list")
        return 0
    if args.status:
        cli.run_command("status")
        return 0
    if args.buy:
        return _run_buy(args.buy, auto_confirm=args.yes, years=args.years)
    if args.years != 1:
        print("--years can only be used with --buy")
        return 1
    if args.get_pricing:
        return _run_get_pricing(args.get_pricing)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
