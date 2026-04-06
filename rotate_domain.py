#!/usr/bin/env python3
"""
Flag-based domain rotation CLI.

This utility complements domain_rotation_cli.py by supporting simple
one-shot flags, as requested in release TODO documentation.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from domain_manager import PorkbunAPIClient


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def load_config() -> Dict[str, Any]:
    """Load domain CLI configuration from disk."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Persist CLI configuration with restrictive file permissions."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def parse_price(value: Any) -> Optional[float]:
    """Parse API price values such as '$2.99' into float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def resolve_credentials(args: argparse.Namespace, config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Resolve API credentials from args, env, or saved config."""
    api_key = args.api_key or os.getenv("PORKBUN_API_KEY") or config.get("api_key")
    api_secret = args.api_secret or os.getenv("PORKBUN_SECRET_KEY") or config.get("api_secret")
    return api_key, api_secret


def update_config_with_credentials(
    config: Dict[str, Any],
    api_key: Optional[str],
    api_secret: Optional[str],
    monthly_budget: Optional[float],
) -> None:
    """Persist credentials and optional budget for future runs."""
    if api_key:
        config["api_key"] = api_key
    if api_secret:
        config["api_secret"] = api_secret
    if monthly_budget is not None:
        config["monthly_budget"] = float(monthly_budget)


def print_search_result(result: Dict[str, Any]) -> None:
    """Render domain search output."""
    domain = result.get("domain", "unknown")
    available = bool(result.get("available"))
    price = result.get("price", "unknown")
    currency = result.get("currency", "USD")

    print(f"Domain: {domain}")
    print(f"Available: {'yes' if available else 'no'}")
    print(f"Price: {price} {currency}")


def command_search(client: PorkbunAPIClient, domain: str) -> int:
    """Search for a specific domain."""
    result = client.search_domain(domain)
    print_search_result(result)
    return 0


def command_buy(
    client: PorkbunAPIClient,
    config: Dict[str, Any],
    domain: str,
    years: int,
    assume_yes: bool,
) -> int:
    """Purchase a specific domain, respecting budget from config."""
    search_result = client.search_domain(domain)
    available = bool(search_result.get("available"))
    if not available:
        print(f"Domain is not available: {domain}")
        return 1

    price = parse_price(search_result.get("price"))
    budget_raw = config.get("monthly_budget")
    current_spending = float(config.get("current_spending", 0.0) or 0.0)
    budget = float(budget_raw) if budget_raw is not None else None

    if budget is not None and price is not None and current_spending + price > budget:
        print(
            "Purchase would exceed monthly budget. "
            f"Current: {current_spending:.2f}, Price: {price:.2f}, Budget: {budget:.2f}"
        )
        return 1

    if not assume_yes:
        print_search_result(search_result)
        confirm = input(f"Purchase {domain} for {search_result.get('price', 'unknown')}? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Purchase cancelled.")
            return 1

    purchase_result = client.purchase_domain(domain, years=years)
    if not purchase_result.get("success"):
        print(f"Purchase failed: {purchase_result.get('message', 'unknown error')}")
        return 1

    now = datetime.now()
    owned_domains = config.get("owned_domains", [])
    if not isinstance(owned_domains, list):
        owned_domains = []

    owned_domains.append(
        {
            "domain": domain,
            "price": price if price is not None else search_result.get("price"),
            "purchased_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365 * years)).isoformat(),
        }
    )
    config["owned_domains"] = owned_domains
    config["active_domain"] = domain

    if price is not None:
        config["current_spending"] = round(current_spending + price, 2)

    save_config(config)
    print(f"Purchased domain: {domain}")
    if purchase_result.get("order_id"):
        print(f"Order ID: {purchase_result['order_id']}")
    return 0


def command_list_owned(client: PorkbunAPIClient) -> int:
    """List domains currently owned in registrar account."""
    domains = client.list_domains()
    if not domains:
        print("No owned domains returned by registrar.")
        return 0

    print("Owned domains:")
    for idx, domain in enumerate(domains, start=1):
        print(f"{idx}. {domain}")
    return 0


def command_get_pricing(client: PorkbunAPIClient, tld: str) -> int:
    """Retrieve TLD pricing."""
    pricing = client.get_pricing(tld)
    if not pricing:
        print(f"No pricing information returned for .{tld}")
        return 1

    print(f"TLD: .{pricing.get('tld', tld)}")
    print(f"Registration: {pricing.get('registration', 'unknown')}")
    print(f"Renewal: {pricing.get('renewal', 'unknown')}")
    print(f"Transfer: {pricing.get('transfer', 'unknown')}")
    print(f"Currency: {pricing.get('currency', 'USD')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Flag-based domain management CLI for Porkbun.",
        epilog=(
            "Examples:\n"
            "  python rotate-domain.py --search example.xyz\n"
            "  python rotate-domain.py --buy example.xyz --years 1 --yes\n"
            "  python rotate-domain.py --list-owned\n"
            "  python rotate-domain.py --get-pricing xyz"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--search", metavar="DOMAIN", help="Check availability/pricing for a domain")
    action_group.add_argument("--buy", metavar="DOMAIN", help="Purchase a specific domain")
    action_group.add_argument("--list-owned", action="store_true", help="List domains in registrar account")
    action_group.add_argument("--get-pricing", metavar="TLD", help="Get pricing for a TLD, e.g. xyz")

    parser.add_argument("--years", type=int, default=1, help="Registration length in years for --buy (default: 1)")
    parser.add_argument("--yes", action="store_true", help="Skip purchase confirmation prompt")
    parser.add_argument("--api-key", help="Porkbun API key (overrides config/env)")
    parser.add_argument("--api-secret", help="Porkbun API secret (overrides config/env)")
    parser.add_argument(
        "--monthly-budget",
        type=float,
        help="Persist monthly budget in config (used for budget checks during --buy)",
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.years < 1:
        print("--years must be >= 1")
        return 2

    config = load_config()
    api_key, api_secret = resolve_credentials(args, config)

    if not api_key or not api_secret:
        print("Missing Porkbun API credentials.")
        print("Provide --api-key/--api-secret, environment variables, or run domain_rotation_cli.py config.")
        return 2

    update_config_with_credentials(config, api_key, api_secret, args.monthly_budget)
    if args.monthly_budget is not None:
        save_config(config)

    client = PorkbunAPIClient(api_key, api_secret)

    if args.search:
        return command_search(client, args.search)
    if args.buy:
        return command_buy(client, config, args.buy, args.years, args.yes)
    if args.list_owned:
        return command_list_owned(client)
    if args.get_pricing:
        return command_get_pricing(client, args.get_pricing)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
