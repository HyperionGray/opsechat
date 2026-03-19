#!/usr/bin/env python3
"""
Simple domain rotation CLI for non-programmers.

Examples:
  python rotate-domain.py --search example.xyz
  python rotate-domain.py --buy example.xyz --years 1 --yes
  python rotate-domain.py --list-owned
  python rotate-domain.py --get-pricing xyz
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from domain_manager import DomainRotationManager, PorkbunAPIClient


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def load_config() -> Dict[str, Any]:
    """Load local domain config file if present."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Persist domain config with restrictive permissions."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def parse_price(value: Any) -> float:
    """Parse mixed numeric/string API prices into float."""
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace("$", "")
            .replace("€", "")
            .replace(",", "")
        )
        return float(cleaned)

    raise ValueError(f"Unsupported price value: {value!r}")


def _serialize_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def serialize_owned_domains(owned_domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Make owned domains JSON-safe for config persistence."""
    serialized: List[Dict[str, Any]] = []
    for item in owned_domains:
        record = dict(item)
        record["purchased_at"] = _serialize_datetime(record.get("purchased_at"))
        record["expires_at"] = _serialize_datetime(record.get("expires_at"))
        serialized.append(record)
    return serialized


def resolve_credentials(config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Resolve API credentials from env first, then local config.
    """
    api_key = os.environ.get("PORKBUN_API_KEY") or config.get("api_key")
    api_secret = os.environ.get("PORKBUN_SECRET_KEY") or config.get("api_secret")

    if not api_key or not api_secret:
        raise ValueError(
            "Porkbun credentials are not configured. Set PORKBUN_API_KEY and "
            "PORKBUN_SECRET_KEY or run: python domain_rotation_cli.py config"
        )

    return api_key, api_secret


def resolve_budget(config: Dict[str, Any]) -> float:
    """Resolve monthly budget from env, config, then default."""
    raw_budget = os.environ.get("DOMAIN_BUDGET", config.get("monthly_budget", 50.0))
    return float(raw_budget)


def list_owned(client: PorkbunAPIClient) -> int:
    """List domains currently owned on registrar account."""
    domains = client.list_domains()
    if not domains:
        print("No owned domains returned.")
        return 0

    print("Owned domains:")
    for domain in domains:
        print(f"- {domain}")
    return 0


def search_domain(client: PorkbunAPIClient, domain: str) -> int:
    """Search for domain availability."""
    result = client.search_domain(domain)
    available = bool(result.get("available"))
    price = result.get("price", "n/a")
    currency = result.get("currency", "USD")

    print(f"Domain: {domain}")
    print(f"Available: {'yes' if available else 'no'}")
    print(f"Price: {price} {currency}")
    return 0


def get_pricing(client: PorkbunAPIClient, tld: str) -> int:
    """Fetch and print pricing for a given TLD."""
    result = client.get_pricing(tld)
    if not result:
        print(f"Unable to fetch pricing for .{tld}")
        return 1

    print(f"TLD: .{result.get('tld', tld)}")
    print(f"Registration: {result.get('registration', 'n/a')} {result.get('currency', 'USD')}")
    print(f"Renewal: {result.get('renewal', 'n/a')} {result.get('currency', 'USD')}")
    print(f"Transfer: {result.get('transfer', 'n/a')} {result.get('currency', 'USD')}")
    return 0


def _build_manager(client: PorkbunAPIClient, config: Dict[str, Any], monthly_budget: float) -> DomainRotationManager:
    manager = DomainRotationManager(api_client=client, monthly_budget=monthly_budget)
    manager.current_spending = float(config.get("current_spending", 0.0))
    return manager


def buy_domain(
    client: PorkbunAPIClient,
    config: Dict[str, Any],
    domain: str,
    years: int,
    assume_yes: bool,
) -> int:
    """Search, confirm, and buy a domain if budget allows."""
    if years < 1:
        print("--years must be at least 1")
        return 1

    budget = resolve_budget(config)
    manager = _build_manager(client, config, budget)

    search_result = client.search_domain(domain)
    if not search_result.get("available"):
        print(f"Domain is not available: {domain}")
        return 2

    try:
        price = parse_price(search_result.get("price"))
    except (TypeError, ValueError):
        print(f"Could not parse price for {domain}: {search_result.get('price')!r}")
        return 1

    print(f"Domain: {domain}")
    print(f"Price: {price:.2f} {search_result.get('currency', 'USD')}")
    print(f"Years: {years}")
    print(f"Budget remaining before purchase: {budget - manager.current_spending:.2f} USD")

    if not assume_yes:
        if not sys.stdin.isatty():
            print("Refusing non-interactive purchase without --yes")
            return 1
        answer = input("Proceed with purchase? (yes/no): ").strip().lower()
        if answer != "yes":
            print("Purchase cancelled.")
            return 1

    # DomainRotationManager enforces monthly budget and tracks owned domains state.
    success = manager.purchase_domain_if_budget_allows(domain, price, years=years)
    if not success:
        print("Purchase failed (budget exceeded or registrar error).")
        return 1

    # Preserve existing config keys and persist updated local state for budget tracking.
    config["monthly_budget"] = budget
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = serialize_owned_domains(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    save_config(config)

    print(f"Purchased and activated domain: {domain}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simple domain rotation CLI",
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
    action_group.add_argument("--search", metavar="DOMAIN", help="Check domain availability")
    action_group.add_argument("--buy", metavar="DOMAIN", help="Buy a domain if available")
    action_group.add_argument("--list-owned", action="store_true", help="List owned domains")
    action_group.add_argument("--get-pricing", metavar="TLD", help="Get registrar pricing for TLD")

    parser.add_argument("--years", type=int, default=1, help="Years to register (default: 1)")
    parser.add_argument("--yes", action="store_true", help="Skip purchase confirmation prompt")
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()

    try:
        api_key, api_secret = resolve_credentials(config)
    except ValueError as exc:
        print(str(exc))
        return 1

    client = PorkbunAPIClient(api_key=api_key, api_secret=api_secret)

    if args.search:
        return search_domain(client, args.search)
    if args.buy:
        return buy_domain(
            client=client,
            config=config,
            domain=args.buy,
            years=args.years,
            assume_yes=args.yes,
        )
    if args.list_owned:
        return list_owned(client)
    if args.get_pricing:
        return get_pricing(client, args.get_pricing)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
