#!/usr/bin/env python3
"""
Simple domain operations CLI for non-programmers.

This script provides a concise interface to domain operations backed by
Porkbun's API:
  - search one domain
  - buy one domain (with confirmation)
  - list owned domains
  - get TLD pricing

Credentials are read from, in order:
  1) --api-key / --api-secret arguments
  2) PORKBUN_API_KEY / PORKBUN_API_SECRET environment variables
  3) ~/.opsechat/domain_config.json (created by domain_rotation_cli.py config)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from domain_manager import PorkbunAPIClient


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def parse_price(value: Any) -> Optional[float]:
    """Normalize API price values into float dollars."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace("$", "").replace(",", "")
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def load_config(config_path: Path = CONFIG_FILE) -> Dict[str, Any]:
    """Load JSON config file if present."""
    if not config_path.exists():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    if isinstance(data, dict):
        return data
    return {}


def save_config(config: Dict[str, Any], config_path: Path = CONFIG_FILE) -> None:
    """Persist config and keep file permissions private."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, sort_keys=True)
    os.chmod(config_path, 0o600)


def resolve_credentials(args: argparse.Namespace, config: Dict[str, Any]) -> Tuple[str, str]:
    """Resolve API credentials from args, env, or persisted config."""
    api_key = (
        args.api_key
        or os.environ.get("PORKBUN_API_KEY")
        or config.get("api_key")
    )
    api_secret = (
        args.api_secret
        or os.environ.get("PORKBUN_API_SECRET")
        or config.get("api_secret")
        or config.get("secret_key")
    )

    if not api_key or not api_secret:
        raise ValueError(
            "Missing Porkbun API credentials. Use --api-key/--api-secret, set "
            "PORKBUN_API_KEY/PORKBUN_API_SECRET, or run "
            "'python domain_rotation_cli.py config'."
        )
    return str(api_key), str(api_secret)


def format_money(value: Optional[float], fallback: str = "unknown") -> str:
    """Format nullable floats as a dollar string."""
    if value is None:
        return fallback
    return f"${value:.2f}"


def command_search(client: PorkbunAPIClient, domain: str) -> int:
    """Search availability and print result."""
    result = client.search_domain(domain)
    available = bool(result.get("available"))
    price = parse_price(result.get("price"))
    currency = result.get("currency", "USD")

    print(f"Domain: {domain}")
    print(f"Available: {'yes' if available else 'no'}")
    if price is None:
        print("Price: unknown")
    else:
        print(f"Price: {price:.2f} {currency}")
    return 0 if available else 1


def command_get_pricing(client: PorkbunAPIClient, tld: str) -> int:
    """Get and print TLD pricing."""
    pricing = client.get_pricing(tld)
    if not pricing:
        print(f"No pricing found for .{tld}")
        return 1

    print(f"TLD: .{tld}")
    print(f"Registration: {pricing.get('registration', 'unknown')}")
    print(f"Renewal: {pricing.get('renewal', 'unknown')}")
    print(f"Transfer: {pricing.get('transfer', 'unknown')}")
    print(f"Currency: {pricing.get('currency', 'USD')}")
    return 0


def command_list_owned(client: PorkbunAPIClient) -> int:
    """List owned domains."""
    domains = client.list_domains()
    if not domains:
        print("No domains owned.")
        return 0

    print("Owned domains:")
    for index, domain in enumerate(domains, start=1):
        print(f"{index}. {domain}")
    return 0


def command_buy(
    client: PorkbunAPIClient,
    domain: str,
    years: int,
    config: Dict[str, Any],
    assume_yes: bool,
    budget_override: Optional[float],
) -> int:
    """Purchase one domain with confirmation and budget checks."""
    search = client.search_domain(domain)
    if not search.get("available"):
        print(f"Domain is not available: {domain}")
        return 1

    price = parse_price(search.get("price"))
    if price is None:
        print("Could not determine domain price; refusing to purchase.")
        return 1

    budget = budget_override if budget_override is not None else config.get("monthly_budget")
    current_spending = parse_price(config.get("current_spending")) or 0.0
    if budget is not None and current_spending + price > float(budget):
        print(
            "Purchase blocked by budget policy: "
            f"{format_money(current_spending)} spent + {format_money(price)} > "
            f"{format_money(float(budget))} monthly budget."
        )
        return 1

    print(f"Domain: {domain}")
    print(f"Price: {price:.2f} USD")
    print(f"Years: {years}")
    if budget is not None:
        remaining_after = float(budget) - (current_spending + price)
        print(f"Budget after purchase: {format_money(remaining_after)}")

    if not assume_yes:
        answer = input("Proceed with purchase? [yes/NO]: ").strip().lower()
        if answer != "yes":
            print("Purchase cancelled.")
            return 1

    result = client.purchase_domain(domain, years=years)
    if not result.get("success"):
        message = result.get("message", "unknown error")
        print(f"Purchase failed: {message}")
        return 1

    print(f"Purchase successful for {domain}")
    if result.get("order_id"):
        print(f"Order ID: {result['order_id']}")

    # Persist spending info if config file is in use.
    config["current_spending"] = round(current_spending + price, 2)
    save_config(config)
    return 0


def run_interactive(args: argparse.Namespace, client: PorkbunAPIClient, config: Dict[str, Any]) -> int:
    """Simple single-shot interactive mode."""
    print("Choose an action:")
    print("1) Search domain")
    print("2) Buy domain")
    print("3) List owned domains")
    print("4) Get TLD pricing")
    choice = input("Selection [1-4]: ").strip()

    if choice == "1":
        domain = input("Domain to search (e.g. example.xyz): ").strip()
        return command_search(client, domain)
    if choice == "2":
        domain = input("Domain to buy (e.g. example.xyz): ").strip()
        years_raw = input("Years [default 1]: ").strip()
        years = 1
        if years_raw:
            try:
                years = int(years_raw)
            except ValueError:
                print("Invalid years value.")
                return 1
        return command_buy(client, domain, years, config, assume_yes=False, budget_override=args.budget)
    if choice == "3":
        return command_list_owned(client)
    if choice == "4":
        tld = input("TLD (e.g. xyz): ").strip().lstrip(".")
        return command_get_pricing(client, tld)

    print("Invalid selection.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Simple domain operations CLI for OpSecHat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python rotate-domain.py --search example.xyz\n"
            "  python rotate-domain.py --buy example.xyz --years 1\n"
            "  python rotate-domain.py --list-owned\n"
            "  python rotate-domain.py --get-pricing xyz\n"
            "  python rotate-domain.py --interactive"
        ),
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--search", metavar="DOMAIN", help="Search one domain for availability")
    group.add_argument("--buy", metavar="DOMAIN", help="Buy one available domain")
    group.add_argument("--list-owned", action="store_true", help="List owned domains")
    group.add_argument("--get-pricing", metavar="TLD", help="Get pricing for one TLD (e.g. xyz)")
    group.add_argument("--interactive", action="store_true", help="Interactive single-action mode")

    parser.add_argument("--years", type=int, default=1, help="Years for --buy (default: 1)")
    parser.add_argument("--yes", action="store_true", help="Skip purchase confirmation for --buy")
    parser.add_argument("--budget", type=float, help="Budget override for purchase checks")
    parser.add_argument("--api-key", help="Porkbun API key")
    parser.add_argument("--api-secret", help="Porkbun API secret")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.years < 1:
        print("Years must be >= 1.")
        return 1

    selected = any(
        [
            args.search,
            args.buy,
            args.list_owned,
            args.get_pricing,
            args.interactive,
        ]
    )
    if not selected:
        parser.print_help()
        return 1

    config = load_config()
    try:
        api_key, api_secret = resolve_credentials(args, config)
    except ValueError as exc:
        print(str(exc))
        return 1

    client = PorkbunAPIClient(api_key, api_secret)

    if args.search:
        return command_search(client, args.search)
    if args.buy:
        return command_buy(
            client=client,
            domain=args.buy,
            years=args.years,
            config=config,
            assume_yes=args.yes,
            budget_override=args.budget,
        )
    if args.list_owned:
        return command_list_owned(client)
    if args.get_pricing:
        return command_get_pricing(client, args.get_pricing.lstrip("."))
    if args.interactive:
        return run_interactive(args, client, config)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
