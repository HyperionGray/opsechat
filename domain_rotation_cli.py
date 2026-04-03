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
from pathlib import Path
from getpass import getpass
from datetime import datetime
from domain_manager import (
    PorkbunAPIClient,
    NamecheapAPIClient,
    DomainRotationManager,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
NAMECHEAP_CONTACT_FIELDS = (
    "FirstName",
    "LastName",
    "Address1",
    "City",
    "StateProvince",
    "PostalCode",
    "Country",
    "Phone",
    "EmailAddress",
)


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


def _serialize_domains(owned_domains):
    """Convert datetime fields to ISO strings for JSON persistence."""
    serialized = []
    for domain in owned_domains:
        item = dict(domain)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, datetime):
                item[key] = value.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_domains(raw_domains):
    """Convert ISO datetime strings back to datetime objects."""
    deserialized = []
    for domain in raw_domains:
        item = dict(domain)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    item[key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep the raw value if it is not parseable.
                    pass
        deserialized.append(item)
    return deserialized


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
    print("This tool supports Porkbun and Namecheap APIs for domain management.\n")
    
    config = load_config()
    
    print("Current configuration:")
    registrar = config.get('registrar', 'porkbun')
    print(f"  Registrar: {registrar}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{str(config['api_key'])[-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    registrar_input = input("Registrar [porkbun/namecheap] (default: porkbun): ").strip().lower()
    if registrar_input in ("", "porkbun", "namecheap"):
        config['registrar'] = registrar_input or "porkbun"
    else:
        print("Invalid registrar choice, keeping previous value")
        config['registrar'] = registrar

    if config['registrar'] == "namecheap":
        print("\nNamecheap setup:")
        print(" - API docs: https://www.namecheap.com/support/api/intro/")
        print(" - API whitelist must include your client IP\n")
        api_user = input("Namecheap API User: ").strip()
        if api_user:
            config['api_user'] = api_user

        api_key = getpass("Namecheap API Key: ").strip()
        if api_key:
            config['api_key'] = api_key

        username = input("Namecheap Username (press Enter to use API user): ").strip()
        if username:
            config['username'] = username

        client_ip = input("Client IP for Namecheap whitelist [default: 127.0.0.1]: ").strip()
        if client_ip:
            config['client_ip'] = client_ip
        elif 'client_ip' not in config:
            config['client_ip'] = "127.0.0.1"

        save_contacts = input(
            "Configure default contact profile now? (needed for purchases) [yes/no]: "
        ).strip().lower()
        if save_contacts == "yes":
            contacts = config.get('default_contacts', {})
            for field in NAMECHEAP_CONTACT_FIELDS:
                value = input(f"  {field}: ").strip()
                if value:
                    contacts[field] = value
            config['default_contacts'] = contacts
    else:
        print("\nPorkbun setup:")
        print(" - API credentials: https://porkbun.com/account/api\n")
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config['api_key'] = api_key
        
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
    
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
    
    registrar = config.get('registrar', 'porkbun')

    if registrar == "namecheap":
        if not config.get('api_user') or not config.get('api_key'):
            print("❌ Error: Namecheap credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_user=config['api_user'],
            api_key=config['api_key'],
            username=config.get('username'),
            client_ip=config.get('client_ip', '127.0.0.1'),
            default_contacts=config.get('default_contacts', {}),
        )
    else:
        if not config.get('api_key') or not config.get('api_secret'):
            print("❌ Error: Porkbun API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config['api_key'], config['api_secret'])

    if registrar not in ("porkbun", "namecheap"):
        print(f"❌ Error: Unsupported registrar '{registrar}'.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = _deserialize_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_domains(manager.owned_domains)
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
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')
        purchased_text = purchased_at.strftime('%Y-%m-%d %H:%M') if hasattr(purchased_at, 'strftime') else str(purchased_at)
        expires_text = expires_at.strftime('%Y-%m-%d') if hasattr(expires_at, 'strftime') else str(expires_at)
        print(f"   Purchased: {purchased_text}")
        print(f"   Expires: {expires_text}")
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
