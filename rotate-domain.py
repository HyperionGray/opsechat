#!/usr/bin/env python3
"""
Simple wrapper CLI for domain rotation workflows.

This script provides a non-interactive interface requested by release planning
docs while reusing the existing domain manager and configuration.
"""

import argparse
import sys

from domain_rotation_cli import get_manager, save_manager_state


def _print_json_like(data):
    for key, value in data.items():
        print(f"{key}: {value}")


def command_status():
    manager, _ = get_manager()
    status = manager.get_budget_status()
    print(f"active_domain: {manager.active_domain or 'none'}")
    _print_json_like(status)


def command_list_owned():
    manager, _ = get_manager()
    domains = manager.get_owned_domains()
    if not domains:
        print("No owned domains")
        return

    for index, domain in enumerate(domains, start=1):
        active = " [ACTIVE]" if domain.get("domain") == manager.active_domain else ""
        years = domain.get("years", 1)
        print(f"{index}. {domain.get('domain', 'unknown')}{active}")
        print(f"   price: {domain.get('price', 'unknown')}")
        print(f"   years: {years}")


def command_get_pricing(tld):
    manager, _ = get_manager()
    pricing = manager.api_client.get_pricing(tld)
    if not pricing:
        print(f"No pricing returned for TLD: {tld}")
        sys.exit(1)
    _print_json_like(pricing)


def command_search(max_price, max_attempts):
    manager, _ = get_manager()
    found = manager.find_cheap_available_domain(max_price=max_price, max_attempts=max_attempts)
    if not found:
        print("No matching domain found")
        sys.exit(1)
    _print_json_like(found)


def command_buy(domain, years):
    manager, config = get_manager()
    if years < 1:
        print("years must be >= 1")
        sys.exit(1)

    result = manager.api_client.search_domain(domain)
    if not result.get("available"):
        print(f"Domain not available: {domain}")
        sys.exit(1)

    raw_price = result.get("price")
    try:
        yearly_price = float(str(raw_price).replace("$", "").replace("€", "").strip())
    except ValueError:
        print(f"Could not parse price: {raw_price}")
        sys.exit(1)

    total_price = round(yearly_price * years, 2)
    success = manager.purchase_domain_if_budget_allows(domain, total_price, years=years)
    if not success:
        print("Purchase failed (budget, API, or registrar error)")
        sys.exit(1)

    manager.active_domain = domain
    save_manager_state(manager, config)
    print(f"Purchased: {domain}")
    print(f"yearly_price: {yearly_price}")
    print(f"years: {years}")
    print(f"total_price: {total_price}")


def build_parser():
    parser = argparse.ArgumentParser(description="Simple domain rotation CLI wrapper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", action="store_true", help="Find one cheap available domain")
    group.add_argument("--buy", metavar="DOMAIN", help="Purchase a specific available domain")
    group.add_argument("--list-owned", action="store_true", help="List owned domains")
    group.add_argument("--get-pricing", metavar="TLD", help="Get registrar pricing for a TLD")
    group.add_argument("--status", action="store_true", help="Show budget and active-domain status")

    parser.add_argument("--max-price", type=float, default=5.0, help="Maximum yearly price for --search")
    parser.add_argument("--max-attempts", type=int, default=10, help="Search attempts for --search")
    parser.add_argument("--years", type=int, default=1, help="Registration years for --buy")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.search:
        command_search(max_price=args.max_price, max_attempts=args.max_attempts)
    elif args.buy:
        command_buy(args.buy, years=args.years)
    elif args.list_owned:
        command_list_owned()
    elif args.get_pricing:
        command_get_pricing(args.get_pricing)
    elif args.status:
        command_status()


if __name__ == "__main__":
    main()
