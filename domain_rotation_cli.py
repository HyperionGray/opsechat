#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It currently supports Porkbun and Namecheap.

Usage:
    python domain_rotation_cli.py list                 # List owned domains
    python domain_rotation_cli.py search               # Search for available cheap domains
    python domain_rotation_cli.py rotate               # Rotate to a new domain
    python domain_rotation_cli.py status               # Show budget status
    python domain_rotation_cli.py config               # Configure API credentials
    python domain_rotation_cli.py pricing --tld xyz    # Show registrar pricing for a TLD
"""

import argparse
import json
import os
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

from domain_manager import DomainRotationManager


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"


def _serialize_domain_records(records):
    """Serialize domain records for JSON storage"""
    serialized = []
    for record in records:
        item = dict(record)
        purchased_at = item.get("purchased_at")
        expires_at = item.get("expires_at")
        if hasattr(purchased_at, "isoformat"):
            item["purchased_at"] = purchased_at.isoformat()
        if hasattr(expires_at, "isoformat"):
            item["expires_at"] = expires_at.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_domain_records(records):
    """Deserialize domain records from JSON storage"""
    deserialized = []
    for record in records or []:
        item = dict(record)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    item[key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep original string if parsing fails
                    pass
        deserialized.append(item)
    return deserialized


def _format_datetime(value, fmt):
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime(fmt)
        except ValueError:
            return value
    return "unknown"


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config):
    """Save configuration to file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)  # Secure permissions
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars: porkbun, namecheap")
    print("Porkbun API docs: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/intro/\n")

    config = load_config()
    current_registrar = config.get("registrar", "porkbun")

    print("Current configuration:")
    print(f"  Registrar: {current_registrar}")
    if config.get("api_key"):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")

    if current_registrar == "namecheap":
        print(f"  API User: {config.get('api_user', 'Not configured')}")
        print(f"  Username: {config.get('username', 'Not configured')}")
        print(f"  Client IP: {config.get('client_ip', 'Not configured')}")
        print(f"  Sandbox: {bool(config.get('sandbox', False))}")

    if config.get("monthly_budget"):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")

    print("\nEnter new values (or press Enter to keep current):\n")

    registrar_input = input(
        f"Registrar [porkbun/namecheap] [{current_registrar}]: "
    ).strip().lower()
    registrar = current_registrar
    if registrar_input in ("porkbun", "namecheap"):
        registrar = registrar_input
    config["registrar"] = registrar

    if registrar == "porkbun":
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config["api_key"] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config["api_secret"] = api_secret

        config.pop("api_user", None)
        config.pop("username", None)
        config.pop("client_ip", None)
        config.pop("sandbox", None)
        config.pop("contact_profile", None)
    else:
        api_user = input(f"Namecheap API User [{config.get('api_user', '')}]: ").strip()
        if api_user:
            config["api_user"] = api_user

        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            config["api_key"] = api_key

        default_username = config.get("username") or config.get("api_user", "")
        username = input(f"Namecheap Username [{default_username}]: ").strip()
        if username:
            config["username"] = username
        elif default_username:
            config["username"] = default_username

        client_ip_default = config.get("client_ip", "127.0.0.1")
        client_ip = input(f"Namecheap Client IP [{client_ip_default}]: ").strip()
        config["client_ip"] = client_ip or client_ip_default

        sandbox_default = "yes" if config.get("sandbox", False) else "no"
        sandbox_input = input(
            f"Use Namecheap sandbox? (yes/no) [{sandbox_default}]: "
        ).strip().lower()
        if sandbox_input in ("yes", "y", "true", "1"):
            config["sandbox"] = True
        elif sandbox_input in ("no", "n", "false", "0"):
            config["sandbox"] = False

        configure_contacts = input(
            "Configure Namecheap contact profile for purchases now? (yes/no) [no]: "
        ).strip().lower()
        if configure_contacts in ("yes", "y"):
            existing = config.get("contact_profile", {})
            profile = {
                "first_name": input(f"First name [{existing.get('first_name', '')}]: ").strip()
                or existing.get("first_name", ""),
                "last_name": input(f"Last name [{existing.get('last_name', '')}]: ").strip()
                or existing.get("last_name", ""),
                "address1": input(f"Address line 1 [{existing.get('address1', '')}]: ").strip()
                or existing.get("address1", ""),
                "address2": input(f"Address line 2 [{existing.get('address2', '')}]: ").strip()
                or existing.get("address2", ""),
                "city": input(f"City [{existing.get('city', '')}]: ").strip()
                or existing.get("city", ""),
                "state_province": input(
                    f"State/Province [{existing.get('state_province', '')}]: "
                ).strip()
                or existing.get("state_province", ""),
                "postal_code": input(f"Postal code [{existing.get('postal_code', '')}]: ").strip()
                or existing.get("postal_code", ""),
                "country": input(
                    f"Country (ISO code, e.g. US) [{existing.get('country', '')}]: "
                ).strip()
                or existing.get("country", ""),
                "phone": input(f"Phone (e.g. +1.5555555555) [{existing.get('phone', '')}]: ").strip()
                or existing.get("phone", ""),
                "email_address": input(f"Email [{existing.get('email_address', '')}]: ").strip()
                or existing.get("email_address", ""),
                "organization_name": input(
                    f"Organization [{existing.get('organization_name', '')}]: "
                ).strip()
                or existing.get("organization_name", ""),
            }
            config["contact_profile"] = profile

        config.pop("api_secret", None)

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


def get_manager():
    """Get configured domain manager"""
    config = load_config()
    registrar = config.get("registrar", "porkbun")
    manager = DomainRotationManager(monthly_budget=config.get("monthly_budget", 50.0))

    try:
        if registrar == "porkbun":
            if not config.get("api_key") or not config.get("api_secret"):
                raise ValueError("Porkbun requires api_key and api_secret")
            manager.configure(
                registrar="porkbun",
                api_key=config["api_key"],
                api_secret=config["api_secret"],
                monthly_budget=config.get("monthly_budget", 50.0),
            )
        elif registrar == "namecheap":
            if not config.get("api_key") or not config.get("api_user"):
                raise ValueError("Namecheap requires api_user and api_key")
            manager.configure(
                registrar="namecheap",
                api_user=config["api_user"],
                api_key=config["api_key"],
                username=config.get("username"),
                client_ip=config.get("client_ip", "127.0.0.1"),
                sandbox=bool(config.get("sandbox", False)),
                contact_profile=config.get("contact_profile", {}),
                monthly_budget=config.get("monthly_budget", 50.0),
            )
        else:
            raise ValueError(f"Unsupported registrar '{registrar}'")
    except ValueError as e:
        print(f"Error: {e}")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if config.get("current_spending"):
        manager.current_spending = config["current_spending"]
    if config.get("owned_domains"):
        manager.owned_domains = _deserialize_domain_records(config["owned_domains"])
    if config.get("active_domain"):
        manager.active_domain = config["active_domain"]

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = _serialize_domain_records(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    save_config(config)


def list_domains():
    """List owned domains"""
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
        print(
            "   Purchased: "
            f"{_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}"
        )
        print(
            "   Expires: "
            f"{_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}"
        )
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()

    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Registrar: {config.get('registrar', 'porkbun')}")
    print("Searching for domains under $5...\n")

    for i in range(5):
        print(f"Attempt {i + 1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)

        if domain_info:
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']}")
        else:
            print("  No cheap domain found in this attempt")

    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain():
    """Rotate to a new domain"""
    manager, config = get_manager()

    print("\n=== Domain Rotation ===\n")
    print(f"Registrar: {config.get('registrar', 'porkbun')}\n")

    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")

    if budget_status["remaining"] < 1:
        print("Insufficient budget remaining this month.")
        return

    print("Searching for available cheap domain...")

    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status["remaining"])
    )

    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return

    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")

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
        print("\nFailed to purchase domain. Check credentials, budget, and contact profile.")


def show_status():
    """Show current status"""
    manager, config = get_manager()

    print("\n=== Domain Rotation Status ===\n")

    budget_status = manager.get_budget_status()

    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Registrar: {config.get('registrar', 'porkbun')}")
    print("\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")

    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"Configure your email system to use: user@{manager.active_domain}")


def show_pricing(tld: str):
    """Show current registrar pricing for a TLD"""
    manager, config = get_manager()
    tld = tld.replace(".", "").lower()

    print("\n=== Registrar Pricing ===\n")
    print(f"Registrar: {config.get('registrar', 'porkbun')}")
    print(f"TLD: .{tld}\n")

    pricing = manager.api_client.get_pricing(tld)
    if not pricing:
        print("No pricing data available for this TLD.")
        return

    currency = pricing.get("currency", "USD")
    print(f"Registration: {pricing.get('registration', 'N/A')} {currency}")
    print(f"Renewal: {pricing.get('renewal', 'N/A')} {currency}")
    print(f"Transfer: {pricing.get('transfer', 'N/A')} {currency}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="OpSecHat Domain Rotation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config             # Configure API credentials
  python domain_rotation_cli.py status             # Show current status
  python domain_rotation_cli.py search             # Search for available domains
  python domain_rotation_cli.py rotate             # Rotate to a new domain
  python domain_rotation_cli.py list               # List owned domains
  python domain_rotation_cli.py pricing --tld xyz  # Show registrar pricing
        """,
    )

    parser.add_argument(
        "command",
        choices=["config", "status", "search", "rotate", "list", "pricing"],
        help="Command to execute",
    )
    parser.add_argument(
        "--tld",
        default="xyz",
        help="TLD to query for pricing command (default: xyz)",
    )

    args = parser.parse_args()

    if args.command == "config":
        configure_api()
    elif args.command == "status":
        show_status()
    elif args.command == "search":
        search_domains()
    elif args.command == "rotate":
        rotate_domain()
    elif args.command == "list":
        list_domains()
    elif args.command == "pricing":
        show_pricing(args.tld)


if __name__ == "__main__":
    main()
