#!/usr/bin/env python3
"""
Compatibility CLI wrapper for domain rotation operations.

This script supports the legacy flag-style CLI documented in release notes
and forwards operations to the maintained domain_rotation_cli module.
"""

import argparse
import json
import sys

from domain_manager import DomainRotationManager
from domain_rotation_cli import (
    configure_api,
    get_manager,
    list_domains,
    rotate_domain,
    save_manager_state,
    search_domains,
    show_status,
)


def search_specific_domain(domain: str) -> int:
    """Check availability for a specific domain."""
    manager, _ = get_manager()
    result = manager.api_client.search_domain(domain)
    price = DomainRotationManager._coerce_price(result.get("price"))
    status = {
        "domain": domain,
        "available": bool(result.get("available")),
        "price": price if price is not None else result.get("price"),
        "currency": result.get("currency", "USD"),
    }
    print(json.dumps(status, indent=2))
    return 0


def buy_specific_domain(domain: str, years: int, yes: bool = False) -> int:
    """Purchase a specific domain with confirmation."""
    if years < 1:
        print("Years must be at least 1.")
        return 1

    manager, config = get_manager()
    search = manager.api_client.search_domain(domain)

    if not search.get("available"):
        print(f"Domain is not available: {domain}")
        return 1

    price = DomainRotationManager._coerce_price(search.get("price"))
    if price is None:
        print(f"Domain price is not valid for purchase: {search.get('price')}")
        return 1

    print(f"Domain: {domain}")
    print(f"Years: {years}")
    print(f"Price: ${price}")

    if not yes:
        confirm = input("Proceed with purchase? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Purchase cancelled.")
            return 1

    if not manager.purchase_domain_if_budget_allows(domain, price, years=years):
        print("Purchase failed due to budget or registrar error.")
        return 1

    manager.active_domain = domain
    save_manager_state(manager, config)
    print(f"Successfully purchased and activated: {domain}")
    return 0


def show_tld_pricing(tld: str) -> int:
    """Show registrar pricing for a TLD."""
    manager, _ = get_manager()
    pricing = manager.api_client.get_pricing(tld)
    if not pricing:
        print(f"No pricing data returned for TLD: {tld}")
        return 1
    print(json.dumps(pricing, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Legacy-compatible domain rotation CLI"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", action="store_true", help="Configure API credentials")
    group.add_argument("--status", action="store_true", help="Show current domain/budget status")
    group.add_argument(
        "--search",
        nargs="?",
        const="",
        metavar="DOMAIN",
        help="Search random cheap domains or inspect specific DOMAIN",
    )
    group.add_argument("--rotate", action="store_true", help="Rotate to a newly purchased domain")
    group.add_argument("--list-owned", action="store_true", help="List owned domains")
    group.add_argument("--get-pricing", metavar="TLD", help="Get pricing for a TLD")
    group.add_argument("--buy", metavar="DOMAIN", help="Buy a specific DOMAIN")
    parser.add_argument("--years", type=int, default=1, help="Years to register (for --buy)")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt for --buy",
    )

    args = parser.parse_args()

    if args.config:
        configure_api()
        return 0
    if args.status:
        show_status()
        return 0
    if args.search is not None:
        if args.search:
            return search_specific_domain(args.search)
        search_domains()
        return 0
    if args.rotate:
        rotate_domain()
        return 0
    if args.list_owned:
        list_domains()
        return 0
    if args.get_pricing:
        return show_tld_pricing(args.get_pricing)
    if args.buy:
        return buy_specific_domain(args.buy, args.years, yes=args.yes)

    return 1


if __name__ == "__main__":
    sys.exit(main())
