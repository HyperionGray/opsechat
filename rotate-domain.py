#!/usr/bin/env python3
"""
Backward-compatible domain rotation CLI wrapper.

Historically, docs referenced `rotate-domain.py`. The project's maintained CLI
is `domain_rotation_cli.py`. This wrapper preserves old command usage and maps
it to the supported implementation.
"""

import argparse
import sys

from domain_rotation_cli import get_manager, load_config, show_status


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rotate-domain compatibility CLI (delegates to domain_rotation_cli.py)"
    )
    parser.add_argument("--search", metavar="DOMAIN", nargs="?", const="", help="Search availability for a domain")
    parser.add_argument("--buy", metavar="DOMAIN", help="Purchase a specific available domain")
    parser.add_argument("--years", type=int, default=1, help="Registration years for --buy (default: 1)")
    parser.add_argument("--list-owned", action="store_true", help="List locally tracked owned domains")
    parser.add_argument("--get-pricing", metavar="TLD", help="Get registrar pricing for a TLD (e.g. xyz)")
    parser.add_argument("--status", action="store_true", help="Show current budget and active domain status")
    return parser


def _require_manager():
    # Reuses existing config validation and exits with helpful messaging if missing
    return get_manager()


def _cmd_search(search_value: str) -> int:
    manager, _config = _require_manager()
    if search_value:
        result = manager.api_client.search_domain(search_value)
        print(result)
        return 0

    domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
    if not domain_info:
        print("No cheap available domain found in this scan.")
        return 1
    print(domain_info)
    return 0


def _cmd_buy(domain: str, years: int) -> int:
    manager, config = _require_manager()
    availability = manager.api_client.search_domain(domain)
    if not availability.get("available"):
        print(f"Domain is not available: {domain}")
        return 1

    price = manager._parse_price(availability.get("price"), default=999.0)
    if not manager.purchase_domain_if_budget_allows(domain, price, years=years):
        print("Purchase denied (budget exceeded or registrar purchase failed).")
        return 1

    config.update(manager.export_state())
    from domain_rotation_cli import save_config

    save_config(config)
    print(f"Purchased and activated: {domain}")
    return 0


def _cmd_list_owned() -> int:
    manager, _config = _require_manager()
    domains = manager.get_owned_domains()
    if not domains:
        print("No owned domains tracked yet.")
        return 0
    for domain in domains:
        marker = " [ACTIVE]" if domain.get("domain") == manager.get_active_domain() else ""
        print(f"{domain.get('domain')}{marker}")
    return 0


def _cmd_get_pricing(tld: str) -> int:
    manager, _config = _require_manager()
    pricing = manager.api_client.get_pricing(tld)
    print(pricing if pricing else {"error": f"Could not fetch pricing for .{tld}"})
    return 0 if pricing else 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.search is not None:
        return _cmd_search(args.search)
    if args.buy:
        return _cmd_buy(args.buy, args.years)
    if args.list_owned:
        return _cmd_list_owned()
    if args.get_pricing:
        return _cmd_get_pricing(args.get_pricing)
    if args.status:
        show_status()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    # Load config once so parser-only invocations still surface missing-config path
    _ = load_config()
    sys.exit(main())
