#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports Porkbun and Namecheap registrars.

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
from domain_manager import PorkbunAPIClient, NamecheapAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


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


def _serialize_owned_domains(owned_domains):
    """Serialize datetime fields for JSON persistence"""
    serialized = []
    for domain in owned_domains:
        record = dict(domain)
        for dt_key in ("purchased_at", "expires_at"):
            value = record.get(dt_key)
            if isinstance(value, datetime):
                record[dt_key] = value.isoformat()
        serialized.append(record)
    return serialized


def _deserialize_owned_domains(owned_domains):
    """Deserialize datetime fields from persisted JSON data"""
    restored = []
    for domain in owned_domains or []:
        record = dict(domain)
        for dt_key in ("purchased_at", "expires_at"):
            value = record.get(dt_key)
            if isinstance(value, str):
                try:
                    record[dt_key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep raw string if format is unexpected.
                    pass
        restored.append(record)
    return restored


def _get_namecheap_contact_from_config(config):
    """Build Namecheap default contact dict from saved config values"""
    keys = [
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
    contact = {}
    for key in keys:
        value = config.get(f"namecheap_contact_{key.lower()}", "").strip()
        if value:
            contact[key] = value
    return contact or None


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars: porkbun, namecheap")
    print("Porkbun API: https://porkbun.com/account/api")
    print("Namecheap API: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    
    print("Current configuration:")
    current_registrar = config.get("registrar", "porkbun")
    print(f"  Registrar: {current_registrar}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    registrar = input("Registrar [porkbun/namecheap] (default: current): ").strip().lower()
    if registrar:
        if registrar not in ("porkbun", "namecheap"):
            print("Invalid registrar; keeping current")
            registrar = current_registrar
        config["registrar"] = registrar
    elif "registrar" not in config:
        config["registrar"] = "porkbun"

    selected_registrar = config.get("registrar", "porkbun")
    api_key = input(f"{selected_registrar.title()} API Key: ").strip()
    if api_key:
        config['api_key'] = api_key

    if selected_registrar == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
        # Clear namecheap-only fields if switching registrars.
        config.pop("api_username", None)
        config.pop("username", None)
        config.pop("client_ip", None)
        config.pop("sandbox", None)
    else:
        api_username = input("Namecheap API Username: ").strip()
        if api_username:
            config["api_username"] = api_username

        username = input("Namecheap account username (blank = API username): ").strip()
        if username:
            config["username"] = username

        client_ip = input("Namecheap allowed Client IP [default: 127.0.0.1]: ").strip()
        if client_ip:
            config["client_ip"] = client_ip
        elif "client_ip" not in config:
            config["client_ip"] = "127.0.0.1"

        sandbox = input("Use Namecheap sandbox? [yes/no, default: no]: ").strip().lower()
        if sandbox in ("yes", "no"):
            config["sandbox"] = sandbox == "yes"
        elif "sandbox" not in config:
            config["sandbox"] = False

        # Optional contact details for automated purchase calls.
        print("\nOptional Namecheap contact details (required for purchases):")
        fields = {
            "firstname": "FirstName",
            "lastname": "LastName",
            "address1": "Address1",
            "city": "City",
            "stateprovince": "StateProvince",
            "postalcode": "PostalCode",
            "country": "Country (ISO code, e.g. US)",
            "phone": "Phone (e.g. +1.5555551212)",
            "emailaddress": "EmailAddress",
        }
        for key, label in fields.items():
            value = input(f"  {label}: ").strip()
            if value:
                config[f"namecheap_contact_{key}"] = value

        # Clear porkbun-only field when on Namecheap.
        config.pop("api_secret", None)
    
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
    
    registrar = config.get("registrar", "porkbun").strip().lower()

    if not config.get('api_key'):
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if registrar == "porkbun":
        if not config.get("api_secret"):
            print("❌ Error: Porkbun API secret not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config['api_key'], config['api_secret'])
    elif registrar == "namecheap":
        if not config.get("api_username"):
            print("❌ Error: Namecheap API username not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_key=config["api_key"],
            api_username=config["api_username"],
            username=config.get("username"),
            client_ip=config.get("client_ip", "127.0.0.1"),
            sandbox=bool(config.get("sandbox", False)),
            default_contact=_get_namecheap_contact_from_config(config),
        )
    else:
        print(f"❌ Error: Unsupported registrar configured: {registrar}")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    manager.add_api_client(registrar, client, make_active=True)
    
    # Load saved state
    if 'current_spending' in config:
        manager.current_spending = config['current_spending']
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
    config['active_registrar'] = manager.active_registrar
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
        registrar = domain.get("registrar", "unknown")
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Registrar: {registrar}")
        print(f"   Price: ${domain['price']}")
        purchased_at = domain.get("purchased_at")
        expires_at = domain.get("expires_at")
        if isinstance(purchased_at, datetime):
            purchased_text = purchased_at.strftime('%Y-%m-%d %H:%M')
        else:
            purchased_text = str(purchased_at) if purchased_at else "unknown"
        if isinstance(expires_at, datetime):
            expires_text = expires_at.strftime('%Y-%m-%d')
        else:
            expires_text = str(expires_at) if expires_at else "unknown"
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
    print(f"Active Registrar: {manager.active_registrar or 'None'}")
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
