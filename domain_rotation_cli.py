#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It integrates with Porkbun API (and can be extended for other registrars).

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
from datetime import datetime
from pathlib import Path
from getpass import getpass

from domain_manager import (
    DomainRotationManager,
    NamecheapAPIClient,
    PorkbunAPIClient,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
SUPPORTED_REGISTRARS = ("porkbun", "namecheap")
NAMECHEAP_CONTACT_FIELDS = [
    "FirstName",
    "LastName",
    "Address1",
    "City",
    "StateProvince",
    "PostalCode",
    "Country",
    "Phone",
    "EmailAddress",
]


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


def _deserialize_datetime(value):
    """Parse datetime from persisted values."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _serialize_owned_domains(domains):
    """Convert datetime objects to ISO-8601 strings for JSON persistence."""
    serialized = []
    for domain in domains or []:
        item = dict(domain)
        for dt_key in ("purchased_at", "expires_at"):
            dt_value = item.get(dt_key)
            if isinstance(dt_value, datetime):
                item[dt_key] = dt_value.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_owned_domains(domains):
    """Restore datetime fields from persisted JSON."""
    parsed = []
    for domain in domains or []:
        item = dict(domain)
        for dt_key in ("purchased_at", "expires_at"):
            item[dt_key] = _deserialize_datetime(item.get(dt_key))
        parsed.append(item)
    return parsed


def _format_datetime(value, fmt):
    """Format persisted datetime values safely for display."""
    dt_value = _deserialize_datetime(value)
    if not dt_value:
        return "Unknown"
    return dt_value.strftime(fmt)


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun and Namecheap APIs for domain management.\n")
    
    config = load_config()
    current_registrar = config.get("registrar", "porkbun").lower()
    if current_registrar not in SUPPORTED_REGISTRARS:
        current_registrar = "porkbun"
    
    print("Current configuration:")
    print(f"  Registrar: {current_registrar}")
    if current_registrar == "porkbun":
        if config.get("api_key"):
            print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
        else:
            print("  API Key: Not configured")
    elif current_registrar == "namecheap":
        if config.get("namecheap_api_key"):
            print(f"  API Key: {'*' * 20}{config['namecheap_api_key'][-4:]}")
        else:
            print("  API Key: Not configured")
        print(f"  API User: {config.get('namecheap_api_user', 'Not configured')}")
        print(f"  Client IP: {config.get('namecheap_client_ip', 'Not configured')}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar_input = input(
        f"Registrar ({'/'.join(SUPPORTED_REGISTRARS)}) [{current_registrar}]: "
    ).strip().lower()
    registrar = registrar_input or current_registrar
    if registrar not in SUPPORTED_REGISTRARS:
        print(f"Invalid registrar '{registrar}', keeping '{current_registrar}'")
        registrar = current_registrar
    config["registrar"] = registrar

    if registrar == "porkbun":
        print("Porkbun API docs: https://porkbun.com/account/api")
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config['api_key'] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
    else:
        print("Namecheap API docs: https://www.namecheap.com/support/api/intro/")
        print("Namecheap requires whitelisted client IP and contact profile for purchases.")
        api_user = input(
            f"Namecheap API User [{config.get('namecheap_api_user', '')}]: "
        ).strip()
        if api_user:
            config["namecheap_api_user"] = api_user

        nc_username = input(
            f"Namecheap Username [{config.get('namecheap_username', config.get('namecheap_api_user', ''))}]: "
        ).strip()
        if nc_username:
            config["namecheap_username"] = nc_username

        nc_api_key = getpass("Namecheap API Key: ").strip()
        if nc_api_key:
            config["namecheap_api_key"] = nc_api_key

        nc_client_ip = input(
            f"Namecheap Client IP (must be whitelisted) [{config.get('namecheap_client_ip', '')}]: "
        ).strip()
        if nc_client_ip:
            config["namecheap_client_ip"] = nc_client_ip

        sandbox_default = "yes" if config.get("namecheap_use_sandbox") else "no"
        sandbox_input = input(
            f"Use Namecheap sandbox? (yes/no) [{sandbox_default}]: "
        ).strip().lower()
        if sandbox_input in ("yes", "no"):
            config["namecheap_use_sandbox"] = sandbox_input == "yes"

        contact_prompt = input(
            "Update Namecheap contact profile now? (yes/no) [no]: "
        ).strip().lower()
        if contact_prompt == "yes":
            existing_contact = dict(config.get("namecheap_contact", {}))
            for field in NAMECHEAP_CONTACT_FIELDS:
                value = input(f"  {field} [{existing_contact.get(field, '')}]: ").strip()
                if value:
                    existing_contact[field] = value
            config["namecheap_contact"] = existing_contact
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0
    
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    registrar = config.get("registrar", "porkbun").lower()
    if registrar not in SUPPORTED_REGISTRARS:
        registrar = "porkbun"

    if registrar == "namecheap":
        required = [
            "namecheap_api_user",
            "namecheap_api_key",
            "namecheap_client_ip",
        ]
        missing = [k for k in required if not config.get(k)]
        if missing:
            print("Error: Namecheap API credentials are incomplete.")
            print(f"Missing fields: {', '.join(missing)}")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)

        client = NamecheapAPIClient(
            api_user=config["namecheap_api_user"],
            api_key=config["namecheap_api_key"],
            username=config.get("namecheap_username", config["namecheap_api_user"]),
            client_ip=config["namecheap_client_ip"],
            use_sandbox=bool(config.get("namecheap_use_sandbox", False)),
            contact_profile=config.get("namecheap_contact", {}),
        )
    else:
        if not config.get('api_key') or not config.get('api_secret'):
            print("Error: Porkbun API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config['api_key'], config['api_secret'])

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    
    # Load saved state
    if config.get('current_spending') is not None:
        manager.current_spending = float(config['current_spending'])
    if config.get('owned_domains'):
        manager.owned_domains = _deserialize_owned_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
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
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}")
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
            print(f"  ✅ Found: {domain_info['domain']} - ${domain_info['price']}")
        else:
            print(f"  ❌ No cheap domain found in this attempt")
    
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
        domain_info['domain'],
        domain_info['price']
    )
    
    if success:
        print(f"\n✅ Successfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\n❌ Failed to purchase domain. Check API credentials and budget.")


def show_status():
    """Show current status"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    
    if manager.active_domain:
        print(f"\n✅ Current burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='OpSecHat Domain Rotation CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config     # Configure API credentials
  python domain_rotation_cli.py status     # Show current status
  python domain_rotation_cli.py search     # Search for available domains
  python domain_rotation_cli.py rotate     # Rotate to a new domain
  python domain_rotation_cli.py list       # List owned domains

Supported registrars:
  - porkbun (default)
  - namecheap
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
