#!/usr/bin/env python3
"""
Simple domain rotation CLI for Porkbun-backed domain management.

Examples:
  python rotate-domain.py --search example.xyz
  python rotate-domain.py --buy example.xyz --years 1
  python rotate-domain.py --list-owned
  python rotate-domain.py --get-pricing xyz
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from domain_manager import (
    DomainRotationManager,
    PorkbunAPIClient,
    parse_price_value,
)


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def _to_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _serialize_owned_domains(domains: List[Dict]) -> List[Dict]:
    serialized = []
    for domain in domains or []:
        entry = dict(domain)
        for field in ("purchased_at", "expires_at"):
            if isinstance(entry.get(field), datetime):
                entry[field] = entry[field].isoformat()
        serialized.append(entry)
    return serialized


def _deserialize_owned_domains(domains: List[Dict]) -> List[Dict]:
    deserialized = []
    for domain in domains or []:
        entry = dict(domain)
        entry["purchased_at"] = _to_datetime(entry.get("purchased_at"))
        entry["expires_at"] = _to_datetime(entry.get("expires_at"))
        deserialized.append(entry)
    return deserialized


def load_config() -> Dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return {}


def save_config(config: Dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
    os.chmod(CONFIG_FILE, 0o600)


def get_manager() -> DomainRotationManager:
    api_key = os.getenv("PORKBUN_API_KEY")
    api_secret = os.getenv("PORKBUN_API_SECRET")
    budget_env = os.getenv("DOMAIN_MONTHLY_BUDGET")
    config = load_config()

    if not api_key:
        api_key = config.get("api_key")
    if not api_secret:
        api_secret = config.get("api_secret")

    if not api_key or not api_secret:
        print(
            "Missing Porkbun credentials. Set PORKBUN_API_KEY and PORKBUN_API_SECRET "
            "or configure them via domain_rotation_cli.py config.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if budget_env:
        try:
            monthly_budget = float(budget_env)
        except ValueError:
            monthly_budget = float(config.get("monthly_budget", 50.0))
    else:
        monthly_budget = float(config.get("monthly_budget", 50.0))

    client = PorkbunAPIClient(api_key, api_secret)
    manager = DomainRotationManager(api_client=client, monthly_budget=monthly_budget)

    manager.current_spending = float(config.get("current_spending", 0.0))
    manager.owned_domains = _deserialize_owned_domains(config.get("owned_domains", []))
    manager.active_domain = config.get("active_domain")

    return manager


def persist_manager_state(manager: DomainRotationManager) -> None:
    config = load_config()
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = _serialize_owned_domains(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    if "monthly_budget" not in config:
        config["monthly_budget"] = manager.monthly_budget
    save_config(config)


def cmd_search(domain: str, manager: DomainRotationManager) -> int:
    result = manager.api_client.search_domain(domain)
    price = parse_price_value(result.get("price"))
    if result.get("available"):
        price_str = f"${price:.2f}" if price is not None else "unknown"
        print(f"AVAILABLE: {domain} ({price_str})")
        return 0
    print(f"UNAVAILABLE: {domain}")
    return 2


def cmd_get_pricing(tld: str, manager: DomainRotationManager) -> int:
    pricing = manager.api_client.get_pricing(tld)
    if not pricing:
        print(f"No pricing available for .{tld}", file=sys.stderr)
        return 1

    registration = parse_price_value(pricing.get("registration"))
    renewal = parse_price_value(pricing.get("renewal"))
    transfer = parse_price_value(pricing.get("transfer"))
    currency = pricing.get("currency", "USD")
    print(f".{tld} pricing ({currency})")
    if registration is not None:
        print(f"  registration: {registration:.2f}")
    if renewal is not None:
        print(f"  renewal:      {renewal:.2f}")
    if transfer is not None:
        print(f"  transfer:     {transfer:.2f}")
    return 0


def cmd_list_owned(manager: DomainRotationManager) -> int:
    domains = manager.get_owned_domains()
    if not domains:
        print("No owned domains tracked in local state.")
        return 0

    for idx, domain in enumerate(domains, 1):
        purchased_at = _to_datetime(domain.get("purchased_at"))
        expires_at = _to_datetime(domain.get("expires_at"))
        purchased_text = (
            purchased_at.strftime("%Y-%m-%d %H:%M")
            if isinstance(purchased_at, datetime)
            else str(domain.get("purchased_at", "unknown"))
        )
        expires_text = (
            expires_at.strftime("%Y-%m-%d")
            if isinstance(expires_at, datetime)
            else str(domain.get("expires_at", "unknown"))
        )
        active = " [ACTIVE]" if domain.get("domain") == manager.active_domain else ""
        print(
            f"{idx}. {domain.get('domain', 'unknown')}{active}\n"
            f"   price: ${float(domain.get('price', 0.0)):.2f}\n"
            f"   purchased: {purchased_text}\n"
            f"   expires:   {expires_text}"
        )
    return 0


def cmd_buy(domain: str, years: int, manager: DomainRotationManager) -> int:
    price_result = manager.api_client.search_domain(domain)
    if not price_result.get("available"):
        print(f"Domain is not available: {domain}", file=sys.stderr)
        return 2

    price = parse_price_value(price_result.get("price"))
    if price is None:
        print("Could not determine domain price from registrar API.", file=sys.stderr)
        return 1

    yearly_total = price * years
    status = manager.get_budget_status()
    if yearly_total > status["remaining"]:
        print(
            f"Budget exceeded: required ${yearly_total:.2f}, remaining ${status['remaining']:.2f}",
            file=sys.stderr,
        )
        return 2

    print(f"Buying {domain} for {years} year(s), estimated total ${yearly_total:.2f}...")
    ok = manager.purchase_domain_if_budget_allows(domain, yearly_total, years=years)
    if not ok:
        print("Purchase failed.", file=sys.stderr)
        return 1

    if years > 1 and manager.owned_domains:
        manager.owned_domains[-1]["expires_at"] = datetime.now() + timedelta(days=365 * years)

    manager.active_domain = domain
    persist_manager_state(manager)
    print(f"Purchased and activated: {domain}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple domain rotation CLI")
    parser.add_argument("--search", metavar="DOMAIN", help="Check domain availability")
    parser.add_argument("--buy", metavar="DOMAIN", help="Buy a specific domain")
    parser.add_argument("--years", type=int, default=1, help="Number of years when buying")
    parser.add_argument("--list-owned", action="store_true", help="List locally tracked owned domains")
    parser.add_argument("--get-pricing", metavar="TLD", help="Get pricing for TLD (e.g. xyz)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    selected_actions = sum(
        bool(x)
        for x in (args.search, args.buy, args.list_owned, args.get_pricing)
    )
    if selected_actions != 1:
        parser.error("Select exactly one action.")

    if args.years < 1:
        print("--years must be >= 1", file=sys.stderr)
        return 2

    manager = get_manager()

    if args.search:
        return cmd_search(args.search, manager)
    if args.buy:
        return cmd_buy(args.buy, args.years, manager)
    if args.list_owned:
        return cmd_list_owned(manager)
    if args.get_pricing:
        return cmd_get_pricing(args.get_pricing.lstrip("."), manager)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
