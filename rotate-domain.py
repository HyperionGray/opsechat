#!/usr/bin/env python3
"""
Flag-based domain rotation CLI.

Implements the release TODO command style:
  python rotate-domain.py --search example.xyz
  python rotate-domain.py --buy example.xyz --years 1
  python rotate-domain.py --list-owned
  python rotate-domain.py --get-pricing xyz
"""

import argparse
import sys
from datetime import datetime, timedelta

from domain_rotation_cli import (
    configure_api,
    get_manager,
    list_domains,
    save_manager_state,
    show_status,
)


def _parse_price(raw_price):
    """Parse registrar price values safely."""
    if raw_price is None:
        return None

    if isinstance(raw_price, (int, float)):
        return float(raw_price)

    if isinstance(raw_price, str):
        cleaned = raw_price.strip().replace("$", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _search_single_domain(domain):
    manager, _ = get_manager()
    result = manager.api_client.search_domain(domain)
    available = bool(result.get("available"))
    print(f"Domain: {domain}")
    print(f"Available: {'yes' if available else 'no'}")
    if "price" in result:
        print(f"Price: {result.get('price')}")
    if "currency" in result:
        print(f"Currency: {result.get('currency')}")
    return 0 if available else 2


def _buy_domain(domain, years, non_interactive):
    manager, config = get_manager()
    search_result = manager.api_client.search_domain(domain)
    if not search_result.get("available"):
        print(f"Domain is not available: {domain}")
        return 2

    price = _parse_price(search_result.get("price"))
    if price is None:
        print("Unable to parse price from registrar response; refusing purchase.")
        return 2

    budget = manager.get_budget_status()
    print(f"Domain: {domain}")
    print(f"Years: {years}")
    print(f"Price: ${price:.2f}")
    print(f"Budget remaining: ${budget['remaining']:.2f}")

    if budget["remaining"] < price:
        print("Budget check failed: not enough remaining budget for this purchase.")
        return 2

    if not non_interactive:
        confirm = input("Proceed with purchase? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Purchase cancelled.")
            return 0

    result = manager.api_client.purchase_domain(domain, years=years)
    if not result.get("success"):
        print(f"Purchase failed: {result.get('message', 'unknown error')}")
        return 1

    manager.current_spending += price
    manager.owned_domains.append(
        {
            "domain": domain,
            "price": price,
            "purchased_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=365 * years),
        }
    )
    if not manager.active_domain:
        manager.active_domain = domain
    save_manager_state(manager, config)
    print(f"Purchase successful. Active domain: {manager.active_domain}")
    return 0


def _get_pricing(tld):
    manager, _ = get_manager()
    pricing = manager.api_client.get_pricing(tld)
    if not pricing:
        print(f"No pricing data returned for .{tld}")
        return 1

    print(f"TLD: .{pricing.get('tld', tld)}")
    print(f"Registration: {pricing.get('registration')}")
    print(f"Renewal: {pricing.get('renewal')}")
    print(f"Transfer: {pricing.get('transfer')}")
    print(f"Currency: {pricing.get('currency', 'USD')}")
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(description="Domain rotation utility")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--search", metavar="DOMAIN", help="Check domain availability")
    actions.add_argument("--buy", metavar="DOMAIN", help="Buy a specific domain")
    actions.add_argument("--list-owned", action="store_true", help="List owned domains")
    actions.add_argument("--get-pricing", metavar="TLD", help="Get pricing for a TLD")
    actions.add_argument("--status", action="store_true", help="Show budget/domain status")
    actions.add_argument("--config", action="store_true", help="Configure API credentials")

    parser.add_argument(
        "--years",
        type=int,
        default=1,
        help="Purchase duration in years (for --buy)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive purchase confirmation",
    )
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.config:
        configure_api()
        return 0
    if args.status:
        show_status()
        return 0
    if args.list_owned:
        list_domains()
        return 0
    if args.search:
        return _search_single_domain(args.search)
    if args.buy:
        if args.years < 1:
            print("--years must be >= 1")
            return 2
        return _buy_domain(args.buy, args.years, args.yes)
    if args.get_pricing:
        return _get_pricing(args.get_pricing)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
