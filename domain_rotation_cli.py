#!/usr/bin/env python3
"""
Domain Rotation CLI for burner email domains.

This tool manages API credentials, searches for cheap domains, rotates domains,
and persists local budget/domain state.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Any, Dict, Tuple

from domain_manager import DomainRotationManager, PorkbunAPIClient


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def load_config() -> Dict[str, Any]:
    """Load configuration from disk."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Persist configuration to disk with secure file permissions."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")


def _serialize_domain_state_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert datetime fields to ISO strings for JSON persistence."""
    payload = dict(entry)
    for key in ("purchased_at", "expires_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


def _parse_iso_datetime(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _deserialize_domain_state_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Restore datetime fields from persisted JSON payloads."""
    payload = dict(entry)
    payload["purchased_at"] = _parse_iso_datetime(payload.get("purchased_at"))
    payload["expires_at"] = _parse_iso_datetime(payload.get("expires_at"))
    return payload


def configure_api() -> None:
    """Configure API credentials and budget."""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun API for domain management.")
    print("You can get API credentials from: https://porkbun.com/account/api\n")

    config = load_config()

    print("Current configuration:")
    if config.get("api_key"):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")

    if config.get("monthly_budget") is not None:
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")

    print("\nEnter new values (or press Enter to keep current):\n")

    api_key = input("Porkbun API Key: ").strip()
    if api_key:
        config["api_key"] = api_key

    api_secret = getpass("Porkbun API Secret: ").strip()
    if api_secret:
        config["api_secret"] = api_secret

    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config["monthly_budget"] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    save_config(config)
    print("\nConfiguration updated successfully")


def get_manager() -> Tuple[DomainRotationManager, Dict[str, Any]]:
    """Build a configured domain manager from local config."""
    config = load_config()

    if not config.get("api_key") or not config.get("api_secret"):
        print("Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    client = PorkbunAPIClient(config["api_key"], config["api_secret"])
    manager = DomainRotationManager(
        api_client=client, monthly_budget=config.get("monthly_budget", 50.0)
    )

    if config.get("current_spending") is not None:
        manager.current_spending = float(config["current_spending"])
    if config.get("owned_domains"):
        manager.owned_domains = [
            _deserialize_domain_state_entry(entry)
            for entry in config.get("owned_domains", [])
            if isinstance(entry, dict)
        ]
    if config.get("active_domain"):
        manager.active_domain = config["active_domain"]

    return manager, config


def save_manager_state(manager: DomainRotationManager, config: Dict[str, Any]) -> None:
    """Persist manager state fields into config."""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = [
        _serialize_domain_state_entry(entry) for entry in manager.owned_domains
    ]
    config["active_domain"] = manager.active_domain
    save_config(config)


def _format_date(value: Any, fmt: str) -> str:
    value = _parse_iso_datetime(value)
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return "unknown"


def list_domains() -> None:
    """List domains currently tracked in local state."""
    manager, _ = get_manager()

    print("\n=== Owned Domains ===\n")
    domains = manager.get_owned_domains()

    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return

    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain.get("domain") == manager.active_domain else ""
        print(f"{i}. {domain.get('domain', 'unknown')}{active}")
        print(f"   Price: ${domain.get('price', 'unknown')}")
        print(f"   Purchased: {_format_date(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_date(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains(max_price: float = 5.0, attempts: int = 10, results: int = 5) -> None:
    """Search and print available cheap domains without purchasing."""
    manager, _ = get_manager()
    max_price = max(0.01, max_price)
    attempts = max(1, attempts)
    results = max(1, results)

    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Searching for up to {results} domains under ${max_price}...\n")

    matches = manager.search_cheap_domains(
        max_price=max_price, max_attempts=attempts, limit=results
    )
    if not matches:
        print("No available domains found with the current constraints.")
        return

    for index, domain_info in enumerate(matches, 1):
        print(f"{index}. {domain_info['domain']} - ${domain_info['price']}")

    print("\nTo purchase one, run: python domain_rotation_cli.py rotate")


def rotate_domain(max_price: float = None, attempts: int = 10, assume_yes: bool = False) -> None:
    """Rotate to a new domain with optional non-interactive confirmation."""
    manager, config = get_manager()
    attempts = max(1, attempts)

    print("\n=== Domain Rotation ===\n")

    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")

    if budget_status["remaining"] < 1:
        print("Insufficient budget remaining this month.")
        return

    if max_price is None:
        max_price = 5.0
    effective_max_price = min(max(0.01, max_price), budget_status["remaining"])

    print(f"Searching for available cheap domain (max ${effective_max_price})...")
    domain_info = manager.find_cheap_available_domain(
        max_price=effective_max_price,
        max_attempts=attempts,
    )

    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return

    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")

    if not assume_yes:
        confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Purchase cancelled.")
            return

    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info["domain"],
        domain_info["price"],
    )

    if success:
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\nFailed to purchase domain. Check API credentials and budget.")


def show_status() -> None:
    """Show active domain and budget summary."""
    manager, _ = get_manager()

    print("\n=== Domain Rotation Status ===\n")

    budget_status = manager.get_budget_status()

    print(f"Active Domain: {manager.active_domain or 'None'}")
    print("\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")

    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"Configure your email system to use: user@{manager.active_domain}")


def set_budget(amount: float) -> None:
    """Update persisted monthly budget."""
    manager, config = get_manager()
    manager.set_monthly_budget(amount)
    config["monthly_budget"] = manager.monthly_budget
    save_manager_state(manager, config)
    print(f"Monthly budget updated to ${manager.monthly_budget}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="OpSecChat Domain Rotation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("config", help="Configure API credentials")
    subparsers.add_parser("status", help="Show current domain and budget status")
    subparsers.add_parser("list", help="List owned domains")

    search_parser = subparsers.add_parser("search", help="Search for cheap domains")
    search_parser.add_argument("--max-price", type=float, default=5.0, help="Maximum price in USD")
    search_parser.add_argument("--attempts", type=int, default=10, help="Search attempts per candidate")
    search_parser.add_argument("--results", type=int, default=5, help="Maximum number of results")

    rotate_parser = subparsers.add_parser("rotate", help="Rotate to a new domain")
    rotate_parser.add_argument("--max-price", type=float, default=None, help="Maximum purchase price in USD")
    rotate_parser.add_argument("--attempts", type=int, default=10, help="Maximum search attempts")
    rotate_parser.add_argument("--yes", action="store_true", help="Skip purchase confirmation prompt")

    budget_parser = subparsers.add_parser("budget", help="View or set monthly budget")
    budget_parser.add_argument("--set", type=float, default=None, help="Set monthly budget amount in USD")

    return parser


def main() -> None:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "config":
        configure_api()
    elif args.command == "status":
        show_status()
    elif args.command == "search":
        search_domains(
            max_price=args.max_price,
            attempts=args.attempts,
            results=args.results,
        )
    elif args.command == "rotate":
        rotate_domain(
            max_price=args.max_price,
            attempts=args.attempts,
            assume_yes=args.yes,
        )
    elif args.command == "list":
        list_domains()
    elif args.command == "budget":
        if args.set is not None:
            set_budget(args.set)
        else:
            show_status()


if __name__ == "__main__":
    main()
