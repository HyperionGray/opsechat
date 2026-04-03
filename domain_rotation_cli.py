#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports Porkbun and Namecheap registrar integrations.

Usage:
    python domain_rotation_cli.py list          # List owned domains
    python domain_rotation_cli.py search        # Search for available cheap domains
    python domain_rotation_cli.py rotate        # Rotate to a new domain
    python domain_rotation_cli.py status        # Show budget status
    python domain_rotation_cli.py config        # Configure API credentials
"""

import argparse
import json
import os
import sys
from pathlib import Path
from getpass import getpass
from datetime import datetime
from domain_manager import DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _serialize_owned_domains(domains):
    """Make owned domain records JSON-safe."""
    serialized = []
    for entry in domains or []:
        record = dict(entry)
        for date_key in ("purchased_at", "expires_at"):
            value = record.get(date_key)
            if isinstance(value, datetime):
                record[date_key] = value.isoformat()
        serialized.append(record)
    return serialized


def _deserialize_owned_domains(domains):
    """Convert serialized datetime fields back to datetime objects."""
    parsed = []
    for entry in domains or []:
        record = dict(entry)
        for date_key in ("purchased_at", "expires_at"):
            value = record.get(date_key)
            if isinstance(value, str):
                try:
                    record[date_key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep original value if it is not ISO-formatted.
                    pass
        parsed.append(record)
    return parsed


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config):
    """Save configuration to file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)  # Secure permissions
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars: porkbun, namecheap")
    print("Porkbun API keys: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    
    print("Current configuration:")
    current_registrar = config.get("registrar", "porkbun")
    print(f"  Registrar: {current_registrar}")
    if config.get("api_key"):
        print(f"  Porkbun API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  Porkbun API Key: Not configured")

    if config.get("namecheap_api_key"):
        print(f"  Namecheap API Key: {'*' * 20}{config['namecheap_api_key'][-4:]}")
    else:
        print("  Namecheap API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar = input(f"Primary Registrar [porkbun/namecheap] [{current_registrar}]: ").strip().lower()
    if not registrar:
        registrar = current_registrar
    if registrar not in {"porkbun", "namecheap"}:
        print("Invalid registrar, keeping current value")
        registrar = current_registrar
    config["registrar"] = registrar

    api_key = input("Porkbun API Key: ").strip()
    if api_key:
        config["api_key"] = api_key

    api_secret = getpass("Porkbun API Secret: ").strip()
    if api_secret:
        config["api_secret"] = api_secret

    nc_api_key = input("Namecheap API Key: ").strip()
    if nc_api_key:
        config["namecheap_api_key"] = nc_api_key

    nc_username = input("Namecheap Username: ").strip()
    if nc_username:
        config["namecheap_username"] = nc_username

    nc_client_ip = input("Namecheap Client IP (whitelisted): ").strip()
    if nc_client_ip:
        config["namecheap_client_ip"] = nc_client_ip

    nc_sandbox = input("Use Namecheap sandbox? [y/N]: ").strip().lower()
    if nc_sandbox in {"y", "yes"}:
        config["namecheap_sandbox"] = True
    elif nc_sandbox in {"n", "no", ""}:
        config["namecheap_sandbox"] = False
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0
    
    save_config(config)
    print("\n[OK] Configuration updated successfully.")


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    manager = DomainRotationManager(monthly_budget=config.get("monthly_budget", 50.0))
    registrar = config.get("registrar", "porkbun")

    # Configure primary registrar
    if registrar == "namecheap":
        if (
            not config.get("namecheap_api_key")
            or not config.get("namecheap_username")
            or not config.get("namecheap_client_ip")
        ):
            print("Error: Namecheap credentials are incomplete.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        manager.configure(
            api_key=config["namecheap_api_key"],
            registrar="namecheap",
            username=config["namecheap_username"],
            client_ip=config["namecheap_client_ip"],
            sandbox=bool(config.get("namecheap_sandbox", False)),
            monthly_budget=config.get("monthly_budget", 50.0),
            make_primary=True,
        )
    else:
        if not config.get("api_key") or not config.get("api_secret"):
            print("Error: Porkbun API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        manager.configure(
            api_key=config["api_key"],
            secret_key=config["api_secret"],
            registrar="porkbun",
            monthly_budget=config.get("monthly_budget", 50.0),
            make_primary=True,
        )

    # Configure fallback registrar when available
    if registrar != "porkbun" and config.get("api_key") and config.get("api_secret"):
        manager.configure(
            api_key=config["api_key"],
            secret_key=config["api_secret"],
            registrar="porkbun",
            monthly_budget=config.get("monthly_budget", 50.0),
            make_primary=False,
        )

    if (
        registrar != "namecheap"
        and config.get("namecheap_api_key")
        and config.get("namecheap_username")
        and config.get("namecheap_client_ip")
    ):
        manager.configure(
            api_key=config["namecheap_api_key"],
            registrar="namecheap",
            username=config["namecheap_username"],
            client_ip=config["namecheap_client_ip"],
            sandbox=bool(config.get("namecheap_sandbox", False)),
            monthly_budget=config.get("monthly_budget", 50.0),
            make_primary=False,
        )

    # Load saved state
    if config.get("current_spending") is not None:
        manager.current_spending = config["current_spending"]
    if config.get("owned_domains"):
        manager.owned_domains = _deserialize_owned_domains(config["owned_domains"])
    if config.get("active_domain"):
        manager.active_domain = config["active_domain"]
    if config.get("active_registrar"):
        manager.active_registrar = config["active_registrar"]

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = _serialize_owned_domains(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    config["active_registrar"] = manager.active_registrar
    save_config(config)


def list_domains():
    """List owned domains"""
    manager, config = get_manager()
    
    print("\n=== Owned Domains ===\n")
    
    domains = manager.get_owned_domains()
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain["domain"] == manager.active_domain else ""
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        if domain.get("registrar"):
            print(f"   Registrar: {domain['registrar']}")

        purchased_at = domain.get("purchased_at")
        if isinstance(purchased_at, datetime):
            purchased_label = purchased_at.strftime("%Y-%m-%d %H:%M")
        else:
            purchased_label = str(purchased_at) if purchased_at else "Unknown"

        expires_at = domain.get("expires_at")
        if isinstance(expires_at, datetime):
            expires_label = expires_at.strftime("%Y-%m-%d")
        else:
            expires_label = str(expires_at) if expires_at else "Unknown"

        print(f"   Purchased: {purchased_label}")
        print(f"   Expires: {expires_label}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            registrar = domain_info.get("registrar", "unknown")
            print(
                f"  Found: {domain_info['domain']} - ${domain_info['price']} via {registrar}"
            )
        else:
            print("  No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain():
    """Rotate to a new domain"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    
    if budget_status['remaining'] < 1:
        print("❌ Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
        return
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info["domain"],
        domain_info["price"],
        registrar=domain_info.get("registrar")
    )
    
    if success:
        registrar = domain_info.get("registrar", manager.active_registrar or "unknown")
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']} via {registrar}")
        save_manager_state(manager, config)
    else:
        print("\nFailed to purchase domain. Check API credentials and budget.")


def show_status():
    """Show current status"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    manager_config = manager.get_config()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Active Registrar: {manager.active_registrar or 'None'}")
    print(f"Configured Registrars: {', '.join(manager_config.get('client_order', [])) or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    
    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='OpSecChat Domain Rotation CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config     # Configure API credentials
  python domain_rotation_cli.py status     # Show current status
  python domain_rotation_cli.py search     # Search for available domains
  python domain_rotation_cli.py rotate     # Rotate to a new domain
  python domain_rotation_cli.py list       # List owned domains
        """
    )
    
    parser.add_argument(
        'command',
        choices=['config', 'status', 'search', 'rotate', 'list'],
        help='Command to execute'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains()
    elif args.command == 'rotate':
        rotate_domain()
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
