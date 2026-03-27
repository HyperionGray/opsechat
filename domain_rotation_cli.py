#!/usr/bin/env python3
"""
Domain Rotation CLI for burner email domains.

This tool supports:
    - interactive and non-interactive configuration
    - JSON output for automation
    - optional environment variable credentials
"""

import argparse
import json
import os
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

from domain_manager import PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def load_config():
    """Load configuration from disk."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except Exception as exc:
        print(f"Error loading config: {exc}")
        return {}


def save_config(config, silent=False):
    """Save configuration to disk with strict permissions."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file_handle:
            json.dump(config, file_handle, indent=2, sort_keys=True)
        os.chmod(CONFIG_FILE, 0o600)
        if not silent:
            print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as exc:
        print(f"Error saving config: {exc}")


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _serialize_domain_entry(entry):
    serialized = dict(entry)
    for key in ("purchased_at", "expires_at"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
    return serialized


def _deserialize_domain_entry(entry):
    deserialized = dict(entry)
    for key in ("purchased_at", "expires_at"):
        parsed_value = _parse_datetime(deserialized.get(key))
        if parsed_value is not None:
            deserialized[key] = parsed_value
    return deserialized


def _format_datetime(value, default="unknown"):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str):
        return value
    return default


def configure_api(args):
    """Configure API credentials and budget."""
    config = load_config()

    updates = {}
    if args.api_key:
        updates["api_key"] = args.api_key
    if args.api_secret:
        updates["api_secret"] = args.api_secret
    if args.monthly_budget is not None:
        if args.monthly_budget <= 0:
            print("Monthly budget must be greater than 0.")
            sys.exit(1)
        updates["monthly_budget"] = float(args.monthly_budget)

    if updates:
        config.update(updates)
        if "monthly_budget" not in config:
            config["monthly_budget"] = 50.0
        save_config(config)
        print("Configuration updated.")
        return

    if args.non_interactive:
        print("No values provided for non-interactive config.")
        print("Use --api-key, --api-secret, and/or --monthly-budget.")
        sys.exit(1)

    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun API for domain management.")
    print("You can get API credentials from: https://porkbun.com/account/api\n")

    print("Current configuration:")
    if config.get("api_key"):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")

    if config.get("monthly_budget"):
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
            parsed_budget = float(budget)
            if parsed_budget <= 0:
                raise ValueError("budget must be positive")
            config["monthly_budget"] = parsed_budget
        except ValueError:
            print("Invalid budget amount, keeping previous value.")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    save_config(config)
    print("Configuration updated successfully.")


def get_manager():
    """Return configured manager and raw config."""
    config = load_config()

    api_key = config.get("api_key") or os.getenv("PORKBUN_API_KEY")
    api_secret = config.get("api_secret") or os.getenv("PORKBUN_SECRET_KEY")

    budget = config.get("monthly_budget")
    if budget is None:
        budget_env = os.getenv("DOMAIN_BUDGET")
        if budget_env:
            try:
                budget = float(budget_env)
            except ValueError:
                print("Invalid DOMAIN_BUDGET value; using default 50.0")
    if budget is None:
        budget = 50.0

    if not api_key or not api_secret:
        print("Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        print("Or set PORKBUN_API_KEY and PORKBUN_SECRET_KEY.")
        sys.exit(1)

    client = PorkbunAPIClient(api_key, api_secret)
    manager = DomainRotationManager(api_client=client, monthly_budget=budget)

    current_spending = config.get("current_spending")
    if isinstance(current_spending, (int, float)):
        manager.current_spending = float(current_spending)

    owned_domains = config.get("owned_domains", [])
    if isinstance(owned_domains, list):
        manager.owned_domains = [
            _deserialize_domain_entry(entry)
            for entry in owned_domains
            if isinstance(entry, dict)
        ]

    active_domain = config.get("active_domain")
    if isinstance(active_domain, str):
        manager.active_domain = active_domain

    return manager, config


def save_manager_state(manager, config, silent=False):
    """Persist mutable manager state back into config file."""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = [
        _serialize_domain_entry(entry)
        for entry in manager.owned_domains
        if isinstance(entry, dict)
    ]
    config["active_domain"] = manager.active_domain
    save_config(config, silent=silent)


def list_domains(args):
    """List owned domains."""
    manager, _ = get_manager()
    domains = manager.get_owned_domains()

    if args.json_output:
        payload = {
            "active_domain": manager.active_domain,
            "domains": [_serialize_domain_entry(entry) for entry in domains],
        }
        print(json.dumps(payload, indent=2))
        return

    print("\n=== Owned Domains ===\n")
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate --yes")
        return

    for index, domain in enumerate(domains, 1):
        domain_name = domain.get("domain", "unknown")
        active_suffix = " [ACTIVE]" if domain_name == manager.active_domain else ""
        print(f"{index}. {domain_name}{active_suffix}")
        print(f"   Price: ${domain.get('price', 'unknown')}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'))}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'))}")
        print()


def search_domains(args):
    """Search for available cheap domains."""
    manager, _ = get_manager()
    attempts = max(1, args.attempts)

    results = []
    for _ in range(attempts):
        domain_info = manager.find_cheap_available_domain(
            max_price=args.max_price, max_attempts=1
        )
        if domain_info:
            results.append({"found": True, **domain_info})
        else:
            results.append({"found": False})

    if args.json_output:
        print(json.dumps(results, indent=2))
        return

    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Searching for domains under ${args.max_price:.2f}...\n")
    for idx, result in enumerate(results, 1):
        print(f"Attempt {idx}/{attempts}...")
        if result["found"]:
            print(f"  Found: {result['domain']} - ${result['price']}")
        else:
            print("  No cheap domain found in this attempt")
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate --yes")


def rotate_domain(args):
    """Rotate to a new domain and persist state."""
    manager, config = get_manager()
    budget_status = manager.get_budget_status()
    max_affordable_price = min(args.max_price, budget_status["remaining"])

    if max_affordable_price <= 0:
        payload = {
            "success": False,
            "reason": "insufficient_budget",
            "budget": budget_status,
        }
        if args.json_output:
            print(json.dumps(payload, indent=2))
        else:
            print("Insufficient budget remaining this month.")
        return

    domain_info = manager.find_cheap_available_domain(max_price=max_affordable_price)
    if not domain_info:
        payload = {
            "success": False,
            "reason": "no_available_domain",
            "budget": budget_status,
        }
        if args.json_output:
            print(json.dumps(payload, indent=2))
        else:
            print("Could not find an available cheap domain within budget.")
        return

    if not args.yes:
        print(f"Found: {domain_info['domain']} for ${domain_info['price']}")
        confirm = input("Proceed with purchase? (yes/no): ").strip().lower()
        if confirm != "yes":
            if args.json_output:
                print(json.dumps({"success": False, "reason": "cancelled"}, indent=2))
            else:
                print("Purchase cancelled.")
            return

    success = manager.purchase_domain_if_budget_allows(
        domain_info["domain"], domain_info["price"]
    )
    if success:
        save_manager_state(manager, config, silent=args.json_output)

    payload = {
        "success": success,
        "domain": domain_info["domain"],
        "price": domain_info["price"],
        "active_domain": manager.active_domain,
        "budget": manager.get_budget_status(),
    }
    if args.json_output:
        print(json.dumps(payload, indent=2))
    else:
        if success:
            print(f"Successfully purchased and activated: {domain_info['domain']}")
        else:
            print("Failed to purchase domain. Check credentials and budget.")


def show_status(args):
    """Show current domain rotation status."""
    manager, _ = get_manager()
    budget_status = manager.get_budget_status()
    payload = {
        "active_domain": manager.active_domain,
        "budget": budget_status,
        "domains_owned": manager.get_owned_domains(),
    }

    if args.json_output:
        payload["domains_owned"] = [
            _serialize_domain_entry(entry) for entry in manager.get_owned_domains()
        ]
        print(json.dumps(payload, indent=2))
        return

    print("\n=== Domain Rotation Status ===\n")
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print("\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"Configure your email system to use: user@{manager.active_domain}")


def build_parser():
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="OpSecChat Domain Rotation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config --api-key pk --api-secret sk --monthly-budget 20
  python domain_rotation_cli.py status --json
  python domain_rotation_cli.py search --attempts 3 --max-price 2.5
  python domain_rotation_cli.py rotate --yes --json
  python domain_rotation_cli.py list --json
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_config = subparsers.add_parser("config", help="Configure API credentials")
    parser_config.add_argument("--api-key", help="Porkbun API key")
    parser_config.add_argument("--api-secret", help="Porkbun API secret")
    parser_config.add_argument(
        "--monthly-budget", type=float, help="Monthly budget in USD"
    )
    parser_config.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail instead of prompting when values are missing",
    )
    parser_config.set_defaults(func=configure_api)

    parser_status = subparsers.add_parser("status", help="Show current status")
    parser_status.add_argument(
        "--json", dest="json_output", action="store_true", help="Output JSON"
    )
    parser_status.set_defaults(func=show_status)

    parser_search = subparsers.add_parser(
        "search", help="Search for available cheap domains"
    )
    parser_search.add_argument("--attempts", type=int, default=5)
    parser_search.add_argument("--max-price", type=float, default=5.0)
    parser_search.add_argument(
        "--json", dest="json_output", action="store_true", help="Output JSON"
    )
    parser_search.set_defaults(func=search_domains)

    parser_rotate = subparsers.add_parser("rotate", help="Rotate to a new domain")
    parser_rotate.add_argument(
        "-y", "--yes", action="store_true", help="Skip interactive confirmation"
    )
    parser_rotate.add_argument("--max-price", type=float, default=5.0)
    parser_rotate.add_argument(
        "--json", dest="json_output", action="store_true", help="Output JSON"
    )
    parser_rotate.set_defaults(func=rotate_domain)

    parser_list = subparsers.add_parser("list", help="List owned domains")
    parser_list.add_argument(
        "--json", dest="json_output", action="store_true", help="Output JSON"
    )
    parser_list.set_defaults(func=list_domains)

    return parser


def main():
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
